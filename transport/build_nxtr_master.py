"""Assemble the NXTR.V0 transport-recipe master (brick 2b, leg 2c).

Combines the three governed/derived feeds into one assembled inventory
workbook (the Ghezzi `_steel_master` pattern: authored master, provenance
per cell, pipeline-side — nxbase will ingest it as source NXTR.V0 via a
flat recipe):

- ``fulfill_car_block.csv``   — EU car intensities by powertrain (FULFILL
                                REF baseline, native EXIOBASE-hybrid units);
- ``derived_recipes_v0.csv``  — rail / navigation / pipeline intensities and
                                HGV load factors derived from nxbase data
                                (UNSD ÷ ITF, Eurostat road_go);
- ``road_eqs_carpda`` snapshot — observed powertrain shares of the car stock
                                (governed, snapshot-only source
                                ESTAT.CARPARK): market shares 2013-2024 and
                                the G/D split of the FULFILL combined block.

Conventions (v0, all declared in the readme sheet):

- tech output metric: **vkm** for road techs (CAR.*, MOTO, BUS, HGV) with a
  SUP row carrying the service yield (pkm/vkm occupancy, tkm/vkm load);
  **the traffic unit itself** (pkm / tkm) for TRN.P/TRN.F, BARGE, SHIP.DOM,
  AIR.DOM, PIPE.T (no SUP row: identity);
- CAR.G / CAR.D share the FULFILL combined liquid intensity (the LP closes
  against the observed UNSD 1221 gasoline/diesel road totals);
- stock shares proxy vkm shares (declared); hybrids fold into G/D (PET/DIE
  aggregates); Hydrogen car excluded (share ~0, not in the taxonomy);
- literature defaults sit on site ``LXX`` / period ``PXX`` placeholders;
- the three leg-1 outliers (FR navigation, DE/IT pipeline) are replaced by
  the default with an anomaly note (never silently implausible).

Output: transport/nxtr_master.xlsx — sheets:

- ``data``     — the recipe-ready flat sheet nxbase ingests (source NXTR.V0,
                 ``from_xlsx_flat``): param (int/SUP) | tech | ref (commodity
                 short, NXB carriers / CN26 jet fuel / NXB service) | site |
                 period | value | unit | provenance;
- ``mkt``      — observed powertrain shares (master-only: the ``mkt``
                 parameter does not admit Technology yet — design decision
                 pending, never improvised);
- ``excluded`` — PIPE.T rows (no honest single carrier until the UNSD 1226
                 product split is derived) and the anomaly register;
- ``readme``   — conventions.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
CARPARK = Path(
    "/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen"
    "/eNextAll - Documents/Databases/nxbase_raw/eurostat/road_eqs_carpda.csv"
)

FULFILL_PROV = "FULFILL_MARIO REF baseline (Golinucci et al. 2025, Apache 2.0)"
CARPARK_PROV = "Eurostat road_eqs_carpda (ESTAT.CARPARK snapshot, stock-share proxy)"

# FULFILL powertrain -> (tech, carrier) ; Diesel and gasoline car handled apart.
FULFILL_TECH = {
    "LPG car": ("CAR.LPG", "LPG"),
    "Methane car": ("CAR.CNG", "NGAS"),
    "Full electric car": ("CAR.E", "ELE"),
}

# carpark mot_nrg aggregates -> tech (hybrids fold into PET/DIE aggregates).
CARPARK_TECH = {"PET": "CAR.G", "DIE": "CAR.D", "LPG": "CAR.LPG",
                "GAS": "CAR.CNG", "ELC": "CAR.E"}
GEO_FIX = {"EL": "GR", "UK": "GB"}

# leg-1 outliers -> literature default with anomaly note.
OUTLIERS = {("BARGE+SHIP.DOM", "FR"), ("PIPE.T", "DE"), ("PIPE.T", "IT")}

# literature defaults (site LXX, period PXX), value in master units.
DEFAULTS = [
    ("int", "MOTO", "GASO", 3.0e-5, "t/vkm",
     "literature default v0 (~3 L/100km class avg) — refine with GFEI/Odyssee"),
    ("int", "BUS", "DIES", 2.5e-4, "t/vkm",
     "literature default v0 (~30 L/100km city/intercity avg)"),
    ("int", "HGV", "DIES", 2.7e-4, "t/vkm",
     "literature default v0 (~32 L/100km loaded avg) — LP closes vs UNSD 1221"),
    ("int", "AIR.DOM", "27101921", 2.0, "MJ/pkm",
     "literature default v0 (domestic aviation; carrier = CN26 jet fuel, the "
     "official container — no NXB bridge needed) — UNSD 1223 fuel is the envelope"),
    ("int", "BARGE", "DIES", 0.5, "MJ/tkm",
     "literature default v0 (inland barge) — country values below where derived"),
    ("int", "SHIP.DOM", "DIES", 0.3, "MJ/tkm",
     "literature default v0 (coastal shipping) — country values below where derived"),
    ("int", "PIPE.T", "MIXED", 0.2, "MJ/tkm",
     "literature default v0 (pipeline; carrier mix = UNSD 1226 product mix)"),
    ("sup", "CAR.G", "MOB.PASS", 1.5, "pkm/vkm",
     "ODYSSEE-MURE EU average car occupancy ~1.5 (declared default v0)"),
    ("sup", "CAR.D", "MOB.PASS", 1.5, "pkm/vkm", "same as CAR.G"),
    ("sup", "CAR.LPG", "MOB.PASS", 1.5, "pkm/vkm", "same as CAR.G"),
    ("sup", "CAR.CNG", "MOB.PASS", 1.5, "pkm/vkm", "same as CAR.G"),
    ("sup", "CAR.E", "MOB.PASS", 1.5, "pkm/vkm", "same as CAR.G"),
    ("sup", "MOTO", "MOB.PASS", 1.1, "pkm/vkm", "literature default v0"),
    ("sup", "BUS", "MOB.PASS", 15.0, "pkm/vkm",
     "literature default v0 (avg bus occupancy)"),
    ("sup", "HGV", "MOB.FRT", 10.0, "tkm/vkm",
     "EU median of observed load factors (fallback; country values below)"),
]

README = [
    ["NXTR.V0 — transport service-layer recipe master (assembled inventory)"],
    [""],
    ["Pattern: Ghezzi _steel_master — authored master, provenance per cell,"],
    ["assembled pipeline-side; nxbase ingests it as source NXTR.V0 (flat recipe)."],
    [""],
    ["Conventions (v0):"],
    ["- road techs (CAR.*, MOTO, BUS, HGV): output metric = vkm; the SUP sheet"],
    ["  carries the service yield (pkm/vkm occupancy, tkm/vkm load factor);"],
    ["- rail/nav/air/pipe techs: output = the traffic unit itself (pkm/tkm),"],
    ["  intensity directly per traffic unit, no SUP row (identity);"],
    ["- CAR.G and CAR.D carry the same FULFILL combined liquid intensity; the"],
    ["  nowcast LP closes against observed UNSD 1221 gasoline/diesel totals;"],
    ["- mkt shares from observed car stock (road_eqs_carpda), stock->vkm proxy"],
    ["  declared; hybrids folded into PET/DIE aggregates; H2 car excluded;"],
    ["- TRN.P/TRN.F (and BARGE/SHIP.DOM) share the per-traffic-unit intensity"],
    ["  derived from the joint UNSD envelope (declared v0 allocation);"],
    ["- literature defaults live on LXX/PXX placeholders; leg-1 outliers"],
    ["  (FR navigation, DE/IT pipeline) fall back to the default with a note."],
]


def read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def main() -> None:
    int_rows: list[dict] = []
    sup_rows: list[dict] = []
    mkt_rows: list[dict] = []

    def add(sheet: list[dict], tech: str, other: str, site: str, period: str,
            value: float, unit: str, prov: str) -> None:
        sheet.append(dict(tech=tech, ref=other, site=site, period=period,
                          value=value, unit=unit, provenance=prov))

    # --- FULFILL car intensities ---
    for r in read_csv(HERE / "data" / "fulfill_car_block.csv"):
        year = f"Y{int(r['year']) % 100:02d}"
        val, country = float(r["value"]), r["country"]
        prov = f"{FULFILL_PROV}, {r['year']}"
        if r["powertrain"] == "Diesel and gasoline car" and r["coef"] == "intensity_liquid":
            add(int_rows, "CAR.G", "GASO", country, year, val, "t/vkm",
                f"{prov}; combined D+G liquid intensity (declared v0)")
            add(int_rows, "CAR.D", "DIES", country, year, val, "t/vkm",
                f"{prov}; combined D+G liquid intensity (declared v0)")
        elif r["powertrain"] in FULFILL_TECH and r["coef"].startswith("intensity"):
            tech, carrier = FULFILL_TECH[r["powertrain"]]
            add(int_rows, tech, carrier, country, year, val, r["unit"].replace("TJ", "TJ"), prov)

    # --- derived intensities (leg 1) ---
    for r in read_csv(HERE / "data" / "derived_recipes_v0.csv"):
        val, site, per = float(r["value"]), r["country"], r["year"]
        prov = r["provenance"]
        if (r["tech"], site) in OUTLIERS:
            continue  # replaced by the default, note below
        if r["tech"] == "TRN.P+TRN.F" and r["coef"].startswith("intensity"):
            carrier = {"intensity_electricity": "ELE", "intensity_liquid": "DIES",
                       "intensity_gas": "NGAS"}[r["coef"]]
            for tech, unit in (("TRN.P", "MJ/pkm"), ("TRN.F", "MJ/tkm")):
                add(int_rows, tech, carrier, site, per, val, unit,
                    f"{prov}; joint P+F per-traffic-unit allocation (v0)")
        elif r["tech"] == "BARGE+SHIP.DOM":
            for tech in ("BARGE", "SHIP.DOM"):
                add(int_rows, tech, "DIES", site, per, val, "MJ/tkm",
                    f"{prov}; joint allocation (v0)")
        elif r["tech"] == "PIPE.T" and r["coef"] == "intensity_total":
            add(int_rows, "PIPE.T", "MIXED", site, per, val, "MJ/tkm", prov)
        elif r["tech"] == "HGV" and r["coef"] == "load_factor_total":
            add(sup_rows, "HGV", "MOB.FRT", site, per, val, "tkm/vkm", prov)

    excluded: list[dict] = []
    for tech, site in OUTLIERS:
        excluded.append(dict(
            tech=tech, ref="-", site=site, period="-", value=None, unit="-",
            reason="ANOMALY: derived value implausible (numerator/denominator "
                   "coverage mismatch) — the LXX default applies instead"))

    # --- observed market shares from the carpark snapshot ---
    stock: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in read_csv(CARPARK):
        if r["mot_nrg"] in CARPARK_TECH and r["OBS_VALUE"]:
            geo = GEO_FIX.get(r["geo"], r["geo"])
            if geo.startswith("EU"):
                continue
            per = f"Y{int(r['TIME_PERIOD']) % 100:02d}"
            stock[(geo, per)][CARPARK_TECH[r["mot_nrg"]]] = float(r["OBS_VALUE"])
    for (geo, per), techs in sorted(stock.items()):
        tot = sum(techs.values())
        if tot <= 0:
            continue
        for tech, v in techs.items():
            add(mkt_rows, tech, "MOB.PASS", geo, per, round(v / tot, 6),
                "share of vkm", CARPARK_PROV)

    # --- defaults ---
    for sheet_name, tech, ref, val, unit, note in DEFAULTS:
        sheet = {"int": int_rows, "sup": sup_rows}[sheet_name]
        add(sheet, tech, ref, "LXX", "PXX", val, unit, note)

    # --- recipe-ready flat sheet: int + SUP; PIPE.T stays master-only ---
    data_rows: list[dict] = []
    for r in int_rows:
        if r["tech"] == "PIPE.T":
            excluded.append(dict(tech="PIPE.T", ref=r["ref"], site=r["site"],
                                 period=r["period"], value=r["value"], unit=r["unit"],
                                 reason="no honest single carrier until the UNSD 1226 "
                                        "product split is derived (master-only)"))
        else:
            data_rows.append({"param": "int", **r})
    data_rows += [{"param": "SUP", **r} for r in sup_rows]

    out = HERE / "data" / "nxtr_master.xlsx"
    with pd.ExcelWriter(out) as xw:
        pd.DataFrame(README).to_excel(xw, sheet_name="readme", index=False, header=False)
        pd.DataFrame(data_rows).to_excel(xw, sheet_name="data", index=False)
        pd.DataFrame(mkt_rows).to_excel(xw, sheet_name="mkt", index=False)
        pd.DataFrame(excluded).to_excel(xw, sheet_name="excluded", index=False)
    print(f"data: {len(data_rows)} (int {sum(1 for r in data_rows if r['param'] == 'int')}"
          f" + SUP {sum(1 for r in data_rows if r['param'] == 'SUP')})  "
          f"mkt: {len(mkt_rows)}  excluded: {len(excluded)}  -> {out}")

    # spot check
    for (g, p) in (("IT", "Y23"), ("DE", "Y23")):
        row = {r["tech"]: r["value"] for r in mkt_rows if r["site"] == g and r["period"] == p}
        print(f"mkt {g} {p}: " + ", ".join(f"{t}={v:.3f}" for t, v in sorted(row.items())))


if __name__ == "__main__":
    main()
