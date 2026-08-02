"""Step 0b — implied power-plant efficiencies from the UNSD balance.

The quantitative arbiter the step-0 selector leaves open: UNSD observes both
sides of the combustible power balance — fuel **inputs** to plants
(transactions ``088`` total and ``0881x/0882x/0883x`` by plant type ×
producer) and electricity/heat **outputs** (``015C*``/``016C*``, the
combustible family). Their ratio is the implied fleet efficiency: a
physically-bounded number that (a) arbitrates the REVIEW countries of
``step0_selection.csv`` with data instead of judgment, and (b) is an early
radar on broken national submissions (η outside physical bands).

Source: the governed UNSD snapshot directly (road_go precedent — the
**CONVERSION_FACTOR column is native material that only lives there**: the
imported rows are mass/volume-native without calorific values). M49 → ISO2
via nxbase's own transform (single mapping, no duplicate).

Conventions (declared):

- input energy = OBS_VALUE × CF (GJ/t or GJ/m³; CF=1 for TJ rows) / 1000;
  rows with no CF are counted and reported, never silently dropped;
- ``DG``/``DS`` (direct geothermal/solar heat into plants) and ``7000``
  (electricity into boilers/heat pumps, ``0889E/H``) are excluded — the
  ratio is combustible-only, consistent with the ``015C/016C`` output side;
- SIEC double counting: ``0100``/``0200`` aggregates are dropped when their
  child leaves report (kept when only the aggregate reports);
- efficiencies: ``eta_elec_plants`` = CE electricity / 0881x fuel;
  ``eta_chp_total`` = CC (electricity + heat) / 0882x fuel;
  ``eta_total`` = all C-family output / 088 total fuel (the headline —
  computable even where the plant-type split is not reported).
- plausibility bands (flags, not filters): elec-only 0.20-0.60;
  CHP total 0.35-0.95; overall 0.20-0.90; anything outside (or >1) is a
  data-quality flag on the country submission.

Output: ``nowcast/step0_efficiency.csv`` (per country × year: the three
etas, coverage diagnostics, the step-0 decision joined) + a printed
arbitration view for the REVIEW countries and flagged UNSD countries.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from nxbase.parsers.runtime import _transform_m49_to_iso2 as m49_to_iso2

SNAPSHOT = Path(
    "/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen"
    "/eNextAll - Documents/Databases/nxbase_raw/unsd_energy/unsd_energy_annual.csv"
)
SELECTION = Path(__file__).parent / "data" / "step0_selection.csv"

IN_TOTAL = "088"
IN_GROUPS = {"elec": ("08811", "08812"), "chp": ("08821", "08822"),
             "heat": ("08831", "08832")}
EXCLUDE_COMMODITIES = {"DG", "DS", "7000"}
AGGREGATES = {"0100": ("0110", "0121", "0129"), "0200": ("0210", "0220")}

BANDS = {"eta_elec_plants": (0.20, 0.60), "eta_chp_total": (0.35, 0.95),
         "eta_total": (0.20, 0.90)}

# --- by-fuel: SIEC input codes <-> by-fuel output transactions (7000T/8000T).
# Input side = 088-total commodity detail; output side = the 01<fuel> view.
# Both sides observed -> implied efficiency per fuel family, convention-free
# (renewables/nuclear never enter: no fuel input in 088 by construction).
FUEL_IN = {
    "coal": {"0100", "0110", "0121", "0129", "0200", "0210", "0220",
             "0311", "0330", "0340"},
    "mgas": {"0350", "0360", "0371", "0379"},
    "peat": {"1100", "1200"},
    "oilshale": {"2000"},
    "gas": {"3000"},
    "oil": {"4100", "4200", "4610", "4630", "4640", "4652", "4661", "4669",
            "4670", "4680", "4694", "4695", "4699"},
    "bio": {"5110", "5120", "5130", "5140", "5150", "5220", "5222", "5290", "5300"},
    "waste": {"6100", "6200"},
}
FUEL_OUT = {
    "coal": {"01CL", "01CP", "01LB"},
    "mgas": {"01MG"},
    "peat": {"01PT"},
    "oilshale": {"01OS"},
    "gas": {"01NG"},
    "oil": {"01CR", "01RF", "01DL", "01PP"},
    "bio": {"01SBF", "01LBF", "01BI", "01BS"},
    "waste": {"01RW", "01NRW"},
}
FUEL_BAND = (0.15, 1.00)   # total (elec + heat) per fuel — wide, physical


def main() -> None:
    # (iso2, year) -> {tx -> {commodity -> TJ}} ; outputs (iso2, year) -> {key -> TJ}
    fuel: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float)))
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    no_cf = 0

    with open(SNAPSHOT) as f:
        for r in csv.DictReader(f):
            tx, com = r["TRANSACTION"], r["COMMODITY"]
            iso2 = m49_to_iso2(r["REF_AREA"])
            if iso2 is None or not r["OBS_VALUE"]:
                continue
            key = (iso2, f"Y{int(r['TIME_PERIOD']) % 100:02d}")
            val = float(r["OBS_VALUE"])
            if tx.startswith("088") and tx not in ("0889E", "0889H"):
                if com in EXCLUDE_COMMODITIES:
                    continue
                cf = r["CONVERSION_FACTOR"]
                if r["UNIT_MEASURE"] == "TJ":
                    tj = val
                elif cf:
                    tj = val * float(cf) / 1e3
                else:
                    no_cf += 1
                    continue
                fuel[key][tx][com] += tj
            elif com == "7000" and tx[:3] in ("015", "016") and tx[3:] in ("C", "CC", "CE"):
                out[key][f"e_{tx[3:]}"] += val * 3.6          # GWh -> TJ
            elif com == "8000" and tx[:3] in ("015", "016") and tx[3:] in ("C", "CC", "CH"):
                out[key][f"h_{tx[3:]}"] += val                 # TJ native
            elif com == "7000T":
                out[key][f"ef_{tx}"] += val * 3.6              # by-fuel elec, GWh -> TJ
            elif com == "8000T":
                out[key][f"hf_{tx}"] += val                    # by-fuel heat, TJ

    def dedup_sum(by_com: dict[str, float]) -> float:
        total = 0.0
        for com, tj in by_com.items():
            if com in AGGREGATES and any(by_com.get(c, 0) > 0 for c in AGGREGATES[com]):
                continue                                       # leaves report -> drop aggregate
            total += tj
        return total

    decisions: dict[str, dict] = {}
    if SELECTION.exists():
        with open(SELECTION) as f:
            decisions = {r["site"]: r for r in csv.DictReader(f)}

    rows_out: list[dict] = []
    for (iso2, yr), groups in sorted(fuel.items()):
        o = out.get((iso2, yr), {})
        f_total = dedup_sum(groups.get(IN_TOTAL, {}))
        f_elec = sum(dedup_sum(groups.get(t, {})) for t in IN_GROUPS["elec"])
        f_chp = sum(dedup_sum(groups.get(t, {})) for t in IN_GROUPS["chp"])
        e_total = o.get("e_C", 0)                              # C = source total (E+CHP)
        h_total = o.get("h_C", 0)
        etas = {
            "eta_total": (e_total + h_total) / f_total if f_total > 0 else None,
            "eta_elec_plants": o.get("e_CE", 0) / f_elec if f_elec > 0 else None,
            "eta_chp_total": (o.get("e_CC", 0) + o.get("h_CC", 0)) / f_chp
            if f_chp > 0 else None,
        }
        # by-fuel: total (elec + heat) output per family / fuel-family input
        by_fuel: dict[str, tuple[float | None, float | None]] = {}
        g088 = groups.get(IN_TOTAL, {})
        for fam in FUEL_IN:
            f_in = dedup_sum({c: v for c, v in g088.items() if c in FUEL_IN[fam]})
            e_out = sum(o.get(f"ef_{t}", 0) for t in FUEL_OUT[fam])
            h_out = sum(o.get(f"hf_{t}", 0) for t in FUEL_OUT[fam])
            if f_in > 0 and (e_out + h_out) > 0:
                by_fuel[fam] = ((e_out + h_out) / f_in, e_out / f_in)
            else:
                by_fuel[fam] = (None, None)

        flags = [k for k, v in etas.items()
                 if v is not None and not (BANDS[k][0] <= v <= BANDS[k][1])]
        flags += [f"eta_{fam}" for fam, (tot, _) in by_fuel.items()
                  if tot is not None and not (FUEL_BAND[0] <= tot <= FUEL_BAND[1])]
        decision = decisions.get(iso2, {}).get("decision", "")
        # mechanical arbitration: a REVIEW country whose UNSD balance is
        # internally coherent (plausible eta) is upgraded to UNSD — the mix
        # distance vs EMBER is then more likely family-mapping noise or an
        # EMBER estimate; an implausible eta keeps it on EMBER.
        if decision.startswith("REVIEW"):
            arbitrated = "UNSD(eta)" if not flags and etas["eta_total"] is not None \
                else "EMBER(eta)"
        else:
            arbitrated = decision
        rows_out.append({
            "site": iso2, "year": yr,
            **{k: (round(v, 3) if v is not None else "") for k, v in etas.items()},
            **{f"eta_{fam}": (round(tot, 3) if tot is not None else "")
               for fam, (tot, _) in by_fuel.items()},
            **{f"eta_{fam}_el": (round(el, 3) if el is not None else "")
               for fam, (_, el) in by_fuel.items()},
            "fuel_in_PJ": round(f_total / 1e3, 1),
            "elec_out_TWh": round(e_total / 3.6 / 1e3, 2),
            "heat_out_PJ": round(h_total / 1e3, 1),
            "flags": ";".join(flags),
            "step0_decision": decision,
            "arbitrated_decision": arbitrated,
        })

    outfile = Path(__file__).parent / "data" / "step0_efficiency.csv"
    with open(outfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print(f"{len(rows_out)} (paese x anno) -> {outfile}  |  righe senza CF: {no_cf}")

    latest: dict[str, dict] = {}
    for r in rows_out:                                         # keep most recent year
        if r["site"] not in latest or r["year"] > latest[r["site"]]["year"]:
            latest[r["site"]] = r

    print("\n=== arbitrato REVIEW (eta plausibile => candidato UNSD) ===")
    for site, r in sorted(latest.items()):
        if r["step0_decision"].startswith("REVIEW"):
            verdict = "eta OK" if not r["flags"] and r["eta_total"] != "" else \
                      (f"FLAG {r['flags']}" if r["flags"] else "no eta")
            print(f"  {site:3} {r['year']} eta_tot={r['eta_total'] or '-':>6} "
                  f"elec={r['eta_elec_plants'] or '-':>6} chp={r['eta_chp_total'] or '-':>6}"
                  f"  -> {verdict}")
    print("\n=== radar: paesi UNSD con eta fuori banda ===")
    for site, r in sorted(latest.items()):
        if r["step0_decision"].startswith("UNSD") and r["flags"]:
            print(f"  {site:3} {r['year']} eta_tot={r['eta_total'] or '-'} "
                  f"elec={r['eta_elec_plants'] or '-'} chp={r['eta_chp_total'] or '-'} "
                  f"flags={r['flags']}")
    tally: dict[str, int] = defaultdict(int)
    for site, r in latest.items():
        if r["step0_decision"]:
            tally[r["arbitrated_decision"].split("|")[0]] += 1
    print(f"\nselezione arbitrata (ultimo anno per paese): {dict(sorted(tally.items()))}")

    print("\nsanity (grandi sistemi) — per plant type e per fuel "
          "(tot = elec+heat / fuel; el = solo elettrico):")
    for site in ("IT", "DE", "FR", "PL", "US", "CN", "JP", "GB"):
        r = latest.get(site)
        if r:
            print(f"  {site:3} {r['year']} eta_tot={r['eta_total']} "
                  f"elec={r['eta_elec_plants']} chp={r['eta_chp_total']}")
            fuels = "  ".join(
                f"{fam}: tot={r[f'eta_{fam}'] or '-'} el={r[f'eta_{fam}_el'] or '-'}"
                for fam in ("coal", "gas", "oil", "bio", "mgas", "waste")
                if r[f"eta_{fam}"] != "")
            print(f"        {fuels}")


if __name__ == "__main__":
    main()
