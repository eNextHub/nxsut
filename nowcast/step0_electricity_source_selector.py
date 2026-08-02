"""Step 0 — electricity generation source selector: UNSD-first, EMBER-as-arbiter.

Decides, per country, whether the nxsut supply-mix update can switch from
EMBER to the richer UNSD generation view (CHP plants, heat, autoproducers
incl. rooftop PV, by-fuel thermal detail — the Merciai-complete accounting)
or must stay on EMBER. Rule (Lorenzo, 2026-08-01): *"abbandonare EMBER
ovunque sia sensato farlo... quando EMBER e UNSD sono ragionevolmente
simili"* — similarity is measured, thresholds declared.

Data access: nxbase query API only (API-first consumer rule) — sources
``UNSD.GEN`` (parameter Supply) and ``EMBER.GEN25`` (parameter Total
output), both ``visibility=open``.

Family mapping (declared; both sides resolve to the EMBER 9-family axis):

- non-thermal families from the UNSD plant-type view (015*/016* on SIEC
  7000, main + autoproducer summed): Nuclear = N; Hydro = HY − PH (EMBER
  excludes pumped-storage output); Solar = S; Wind = W; Other renewables =
  G + T (geothermal + tide/wave).
- thermal families from the UNSD by-fuel view (01<fuel> on SIEC 7000T):
  Coal = CL + CP + LB; Gas = NG; Other fossil = CR + RF + DL + PP + OS +
  PT + MG + NRW (EMBER counts peat, oil shale, manufactured gases and
  non-renewable waste there); Bioenergy = BI + SBF + LBF + BS + RW
  (renewable municipal waste is bioenergy in EMBER).

Similarity per (country, year with both sources):

- ``TVD``  = 0.5 * sum |share_UNSD − share_EMBER|   (mix distance, 0-1)
- ``dTOT`` = |total_UNSD − total_EMBER| / total_EMBER (level distance;
  a ~2% gross-vs-net bias is expected and tolerated)

Selection on the most recent common year (usually 2023). The consumed
object is the **mix** (``update_supply_mix``) — levels are reconciled by
the LP anchors — so the decision rides on TVD; dTOT only flags:

- **UNSD**   if TVD ≤ 0.05
- **EMBER**  if TVD > 0.15, or UNSD missing entirely
- **REVIEW** otherwise (borderline — human call)
- suffix ``|dtot`` when dTOT > 0.25 (coverage smell, whatever the mix says)

Output: ``nowcast/step0_selection.csv`` (one row per country: decision,
metrics per year, CHP/autoproducer share gained by switching) + a printed
summary. Thresholds are constants below — tune and re-run.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "http://127.0.0.1:8000"
UNSD_SOURCE = "UNSD Energy Statistics — electricity & heat production 2021-2023"
EMBER_SOURCE = "EMBER Yearly Electricity Data (generation) 2025"

FAMILIES = ["Coal", "Gas", "OtherFossil", "Bioenergy", "Nuclear",
            "Hydro", "Solar", "Wind", "OtherRenewables"]

# UNSD plant-type sources (commodity 7000, 015/016 summed) -> family.
# Source TOTALS only (S contains SP/ST; leaves would double count). "Other
# sources" and "chemical heat" are non-combustible (absent from the by-fuel
# view, no double count) and EMBER would class them as Other Fossil.
_PLANT = {"N": "Nuclear", "HY": "Hydro", "S": "Solar", "W": "Wind",
          "G": "OtherRenewables", "T": "OtherRenewables",
          "O": "OtherFossil", "H": "OtherFossil"}
_PUMPED = "PH"  # subtracted from Hydro
# disjoint source totals (for the autoproducer diagnostic — leaves excluded)
_TOTALS = {"C", "G", "H", "N", "O", "S", "HY", "T", "W"}
# UNSD by-fuel codes (commodity 7000T) -> family
_FUEL = {
    "CL": "Coal", "CP": "Coal", "LB": "Coal",
    "NG": "Gas",
    "CR": "OtherFossil", "RF": "OtherFossil", "DL": "OtherFossil",
    "PP": "OtherFossil", "OS": "OtherFossil", "PT": "OtherFossil",
    "MG": "OtherFossil", "NRW": "OtherFossil",
    "BI": "Bioenergy", "SBF": "Bioenergy", "LBF": "Bioenergy",
    "BS": "Bioenergy", "RW": "Bioenergy",
}
_EMBER = {"Coal": "Coal", "Gas": "Gas", "Other Fossil": "OtherFossil",
          "Bioenergy": "Bioenergy", "Nuclear": "Nuclear", "Hydro": "Hydro",
          "Solar": "Solar", "Wind": "Wind", "Other Renewables": "OtherRenewables"}

TVD_UNSD = 0.05    # accept UNSD at or below this mix distance
TVD_EMBER = 0.15   # force EMBER above this
DTOT_EMBER = 0.25  # level-gap flag (|dtot suffix), not a decision gate


def fetch(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def main() -> None:
    # --- UNSD: family TWh per (site, year), + CHP/autoproducer diagnostics ---
    unsd: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    chp_auto: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rows = fetch({"parameter": "Supply", "source": UNSD_SOURCE, "limit": "100000"})
    print(f"UNSD.GEN rows: {len(rows)}")
    for r in rows:
        commodity = r["item_1"][2:]                      # c_<SIEC>
        parts = r["item_2"].split("-")                   # a_<tx>-<site>-<period>
        if len(parts) != 3:
            continue
        tx, site, per = parts[0][2:], parts[1], parts[2]
        twh = float(r["value"]) / 1e3                    # GWh -> TWh (7000/7000T rows)
        key = (site, per)
        if commodity == "7000" and tx[:3] in ("015", "016"):
            suffix = tx[3:]
            if suffix in _PLANT:
                unsd[key][_PLANT[suffix]] += twh
            elif suffix == _PUMPED:
                unsd[key]["Hydro"] -= twh
            # CHP + autoproducer electricity (what EMBER cannot see)
            if suffix.endswith("C") and len(suffix) == 2:
                chp_auto[key]["chp"] += twh
            if tx.startswith("016") and suffix in _TOTALS:
                chp_auto[key]["auto"] += twh
        elif commodity == "7000T" and tx.startswith("01"):
            code = tx[2:]
            if code in _FUEL:
                unsd[key][_FUEL[code]] += twh
        elif commodity == "7000" and tx == "019":
            chp_auto[key]["net_total"] = twh

    # --- EMBER: family TWh per (site, year) ---
    ember: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rows = fetch({"parameter": "Total output", "source": EMBER_SOURCE, "limit": "100000"})
    print(f"EMBER rows: {len(rows)}")
    for r in rows:
        fam = _EMBER.get(r.get("i1_name") or "")
        parts = r["item_1"].split("-")                   # a_<tech>-EXX-<site>-<period>
        if fam and len(parts) == 4:
            ember[(parts[2], parts[3])][fam] += float(r["value"])  # TWh native

    # --- compare on common (site, year) ---
    out_rows: list[dict] = []
    sites = sorted({s for s, _ in unsd} & {s for s, _ in ember})
    for site in sites:
        years = sorted({p for s, p in unsd if s == site} & {p for s, p in ember if s == site})
        if not years:
            continue
        metrics = {}
        for per in years:
            u, e = unsd[(site, per)], ember[(site, per)]
            tu, te = sum(u.values()), sum(e.values())
            if te <= 0 or tu <= 0:
                continue
            tvd = 0.5 * sum(abs(u.get(f, 0) / tu - e.get(f, 0) / te) for f in FAMILIES)
            dtot = abs(tu - te) / te
            metrics[per] = (tvd, dtot, tu, te)
        if not metrics:
            continue
        per = max(metrics)                               # most recent common year
        tvd, dtot, tu, te = metrics[per]
        # The consumed object is the MIX (update_supply_mix); levels are
        # reconciled by the LP anchors. Decide on TVD; extreme level gaps
        # (gross-vs-net is ~2%, so >25% means coverage issues) only flag.
        if tvd <= TVD_UNSD:
            decision = "UNSD"
        elif tvd > TVD_EMBER:
            decision = "EMBER"
        else:
            decision = "REVIEW"
        if dtot > DTOT_EMBER:
            decision += "|dtot"
        diag = chp_auto[(site, per)]
        thermal = sum(unsd[(site, per)].get(f, 0) for f in
                      ("Coal", "Gas", "OtherFossil", "Bioenergy"))
        out_rows.append({
            "site": site, "decision": decision, "year": per,
            "tvd": round(tvd, 4), "dtot": round(dtot, 4),
            "unsd_twh": round(tu, 2), "ember_twh": round(te, 2),
            "chp_share_of_thermal": round(diag.get("chp", 0) / thermal, 3) if thermal else "",
            "autoproducer_share": round(diag.get("auto", 0) / tu, 3) if tu else "",
            "years_compared": ";".join(f"{p}:tvd={m[0]:.3f}" for p, m in sorted(metrics.items())),
        })

    out = Path(__file__).parent / "data" / "step0_selection.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    tally = defaultdict(int)
    for r in out_rows:
        tally[r["decision"]] += 1
    print(f"\n{len(out_rows)} paesi confrontati -> {dict(tally)}  ({out})")
    ember_only = sorted({s for s, _ in ember} - {s for s, _ in unsd})
    print(f"solo EMBER (nessun dato UNSD 7000): {len(ember_only)} siti -> EMBER by default")
    print("\nsample (big emitters + REVIEW):")
    for r in out_rows:
        if r["site"] in ("IT", "DE", "FR", "ES", "PL", "US", "CN", "JP", "IN", "GB") \
                or r["decision"].startswith("REVIEW"):
            print(f"  {r['site']:3} {r['decision']:7} tvd={r['tvd']:.3f} dtot={r['dtot']:.3f} "
                  f"UNSD={r['unsd_twh']:>8} EMBER={r['ember_twh']:>8} "
                  f"chp/thermal={r['chp_share_of_thermal']} auto={r['autoproducer_share']}")


if __name__ == "__main__":
    main()
