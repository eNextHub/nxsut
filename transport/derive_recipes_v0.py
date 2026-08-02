"""Derive transport-recipe coefficients from nxbase-governed data (brick 2b, leg 1).

Half of the NXTR.V0 recipe table needs **no external source** — it is derived
from data already governed in nxbase:

- rail intensity (MJ per traffic unit, by carrier): UNSD `1222` energy use
  (electricity + gas oil) ÷ (ITF/ESTAT rail pkm + ITF rail tkm), per country;
  passenger/freight allocated per traffic unit (declared v0 assumption);
- domestic navigation intensity (MJ/tkm): UNSD `1224` ÷ ITF (IWW + coastal)
  tkm — allocated per tkm between BARGE and SHIP.DOM (declared);
- pipeline intensity (MJ/tkm): UNSD `1226` ÷ ITF pipeline tkm;
- domestic aviation: UNSD `1223` fuel observed, but no governed pkm — the
  intensity stays a literature default in NXTR.V0 (the fuel total remains the
  reconciling envelope); reported here for reference;
- HGV load factor (tkm/vkm): Eurostat `road_go_ta_tott` MIO_TKM ÷ MIO_VKM by
  operation, read from the governed snapshot (the vkm slice is native there).

Data access: nxbase query API (API-first, provenance logged) + the governed
Eurostat snapshot for the vkm slice. Mass fuels are converted with declared
LHVs (v0; refinable from the UNSD CONVERSION_FACTOR column later).

Output: transport/derived_recipes_v0.csv — tidy (tech, country, year, coef,
value, unit, provenance), the feed for the NXTR.V0 assembled master.
"""

from __future__ import annotations

import csv
import io
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = os.environ.get("NXBASE_API", "http://127.0.0.1:8000")

# Declared v0 lower heating values, GJ/t (IPCC 2006 defaults, net calorific).
LHV_GJ_T = {"4670": 43.0, "4661": 44.1, "4680": 40.4, "4652": 44.3}
# energy units -> MJ
TO_MJ = {"TJ": 1e6, "GWh": 3.6e6, "t": None}  # t handled via LHV per SIEC code

YEARS = ("Y21", "Y22", "Y23")


def fetch(params: dict) -> list[dict]:
    q = urllib.parse.urlencode(params)
    url = f"{API}/data.csv?{q}"
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def energy_mj(row: dict) -> float | None:
    """Convert one UNSD.USE row to MJ (None if not convertible)."""
    unit, val = row["unit"], float(row["value"])
    if unit in ("TJ", "GWh"):
        return val * TO_MJ[unit]
    if unit == "t":
        lhv = LHV_GJ_T.get(row.get("_siec", ""))
        return val * lhv * 1e3 if lhv else None
    return None


def main() -> None:
    out_rows: list[dict] = []

    # --- governed energy use by transport mode (UNSD.USE) ---
    energy: dict[tuple[str, str, str], float] = defaultdict(float)  # (ires, site, year) -> MJ
    by_carrier: dict[tuple[str, str, str, str], float] = defaultdict(float)
    for ires, label in [("1222", "rail"), ("1223", "aviation"),
                        ("1224", "navigation"), ("1226", "pipeline")]:
        rows = fetch({"parameter": "Use", "source": "UNSD Energy Statistics",
                      "activity": {"1222": "Consumption by rail",
                                   "1223": "Consumption by domestic aviation",
                                   "1224": "Consumption by domestic navigation",
                                   "1226": "Consumption by pipeline transport"}[ires],
                      "limit": "100000"})
        for r in rows:
            parts = r["item_2"].split("-")  # a_<ires>-<site>-<period>
            if len(parts) != 3:
                continue
            site, per = parts[1], parts[2]
            if per not in YEARS:
                continue
            r["_siec"] = r["item_1"][2:]  # c_<code>
            mj = energy_mj(r)
            if mj is None:
                continue
            energy[(ires, site, per)] += mj
            carrier = "electricity" if r["unit"] == "GWh" else (
                "gas" if r["_siec"] == "3000" else "liquid")
            by_carrier[(ires, site, per, carrier)] += mj
        print(f"UNSD {ires} ({label}): {len(rows)} righe")

    # --- governed activity (ITF pkm/tkm) ---
    act: dict[tuple[str, str, str], float] = defaultdict(float)  # (key, site, year) -> M unit
    for key, activity, source in [
        ("rail_pkm", "Rail passenger transport", "International Transport Forum"),
        ("rail_tkm", "Rail freight transport", "International Transport Forum"),
        ("iww_tkm", "Inland waterways freight transport", "International Transport Forum"),
        ("coast_tkm", "Coastal shipping freight transport", "International Transport Forum"),
        ("pipe_tkm", "Pipeline freight transport", "International Transport Forum"),
    ]:
        rows = fetch({"parameter": "Total output", "source": source,
                      "activity": activity, "limit": "100000"})
        for r in rows:
            parts = r["item_1"].split("-")  # a_<act>-EXX-<site>-<period>
            if len(parts) != 4:
                continue
            site, per = parts[2], parts[3]
            if per in YEARS:
                act[(key, site, per)] += float(r["value"])  # Mpkm/Mtkm
        print(f"ITF {key}: {len(rows)} righe")

    # --- derived intensities (MJ per traffic unit) ---
    sites = sorted({s for (_, s, _) in energy})
    for site in sites:
        for per in YEARS:
            # rail: E(1222) / (pkm + tkm), per carrier
            tu = act.get(("rail_pkm", site, per), 0) + act.get(("rail_tkm", site, per), 0)
            if tu > 0 and (("1222", site, per) in energy):
                for carrier in ("electricity", "liquid", "gas"):
                    e = by_carrier.get(("1222", site, per, carrier), 0.0)
                    if e > 0:
                        out_rows.append(dict(
                            tech="TRN.P+TRN.F", country=site, year=per,
                            coef=f"intensity_{carrier}", value=round(e / (tu * 1e6), 4),
                            unit="MJ/traffic-unit",
                            provenance="derived: UNSD.USE 1222 / (ITF rail pkm+tkm)"))
            # navigation: E(1224) / (iww + coastal tkm)
            ntu = act.get(("iww_tkm", site, per), 0) + act.get(("coast_tkm", site, per), 0)
            if ntu > 0 and (("1224", site, per) in energy):
                out_rows.append(dict(
                    tech="BARGE+SHIP.DOM", country=site, year=per,
                    coef="intensity_liquid",
                    value=round(energy[("1224", site, per)] / (ntu * 1e6), 4),
                    unit="MJ/tkm",
                    provenance="derived: UNSD.USE 1224 / (ITF iww+coastal tkm)"))
            # pipeline
            ptu = act.get(("pipe_tkm", site, per), 0)
            if ptu > 0 and (("1226", site, per) in energy):
                out_rows.append(dict(
                    tech="PIPE.T", country=site, year=per, coef="intensity_total",
                    value=round(energy[("1226", site, per)] / (ptu * 1e6), 4),
                    unit="MJ/tkm",
                    provenance="derived: UNSD.USE 1226 / ITF pipeline tkm"))
            # aviation: fuel observed, no governed pkm -> envelope only
            if ("1223", site, per) in energy:
                out_rows.append(dict(
                    tech="AIR.DOM", country=site, year=per, coef="fuel_envelope",
                    value=round(energy[("1223", site, per)] / 1e6, 1), unit="TJ",
                    provenance="observed: UNSD.USE 1223 (intensity = literature default in v0)"))

    # --- HGV load factors from the governed Eurostat snapshot ---
    raw_root = next((t for t in os.environ.get("NXBASE_RAW_ROOT", "").split(";") if t.strip()), "")
    snap = Path(raw_root) / "eurostat" / "road_go_ta_tott.csv"
    if snap.exists():
        acc: dict[tuple[str, str, str, str], float] = {}
        with open(snap) as f:
            for r in csv.DictReader(f):
                if (r["tra_oper"] == "TOTAL" and r["tra_type"] in ("TOTAL", "HIRE", "OWN")
                        and r["unit"] in ("MIO_TKM", "MIO_VKM") and r["OBS_VALUE"]):
                    yr = "Y" + r["TIME_PERIOD"][-2:]
                    if yr in YEARS:
                        geo = {"EL": "GR", "UK": "GB"}.get(r["geo"], r["geo"])
                        if geo in ("EU27_2020", "EU28", "EU27_2007", "EU25", "EU15"):
                            continue
                        acc[(geo, yr, r["tra_type"], r["unit"])] = float(r["OBS_VALUE"])
        for (geo, yr, ttype) in sorted({(g, y, t) for (g, y, t, _) in acc}):
            tkm = acc.get((geo, yr, ttype, "MIO_TKM"))
            vkm = acc.get((geo, yr, ttype, "MIO_VKM"))
            if tkm and vkm and vkm > 0:
                out_rows.append(dict(
                    tech="HGV", country=geo, year=yr,
                    coef=f"load_factor_{ttype.lower()}", value=round(tkm / vkm, 3),
                    unit="tkm/vkm",
                    provenance="observed: Eurostat road_go_ta_tott MIO_TKM/MIO_VKM"))
    else:
        print(f"snapshot road_go non trovato in {snap} — load factors saltati")

    out = Path(__file__).parent / "data" / "derived_recipes_v0.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tech", "country", "year", "coef",
                                          "value", "unit", "provenance"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nscritte {len(out_rows)} righe -> {out}")


if __name__ == "__main__":
    main()
