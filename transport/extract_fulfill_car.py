"""Extract the EU car block from FULFILL_MARIO shocks (brick 2b, leg 2).

FULFILL_MARIO (Golinucci et al. 2025, Ecological Economics; Apache 2.0,
in-house) carries, per EXIOBASE-hybrid region and scenario year, the z
coefficients of five car powertrain activities and their market shares into
the "Car mobility" commodity. This script extracts the REF baseline
(measure "0" = background only) for 2011 / 2020 / 2025 into a tidy block
for the NXTR.V0 assembled master.

Faithfulness rules (nxbase philosophy):

- values stay **native** (EXIOBASE-hybrid units: t/km for all mass carriers
  — natural gas included, per Classifications_v_3_3_18 "tonnes" — TJ/km for
  electricity only; denominator = vehicle-km) — the master normalises, with
  the conversion declared;
- the recipe intensity is the **sum over origin regions** of each carrier
  input (the origin split is trade information — BACI's job, not the
  recipe's); the sum is validated against the known IT 2020 decode;
- market shares are read as-is (row region == column region block);
- nothing is filtered beyond the car block: all regions (RoW included) and
  all five powertrains (Hydrogen car too, even if ~0 in 2020 — the master
  decides what enters the taxonomy).

Output: transport/fulfill_car_block.csv
(country, year, powertrain, coef, value, unit, provenance).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

FULFILL = Path("/Users/lorenzorinaldi/Documents/GitHub/FULFILL_MARIO")
FILES = {y: FULFILL / "Shocks" / "filled_files" / f"REF_0_{y}.xlsx" for y in (2011, 2020, 2025)}

CARS = [
    "Diesel and gasoline car",
    "LPG car",
    "Methane car",
    "Hydrogen car",
    "Full electric car",
]

# carrier row sector -> (coef label, native EXIOBASE-hybrid unit per vkm)
CARRIERS = {
    "Liquid fuels": ("intensity_liquid", "t/vkm"),
    "Liquefied Petroleum Gases (LPG)": ("intensity_lpg", "t/vkm"),
    "Natural gas and services related to natural gas extraction; excluding surveying":
        ("intensity_gas", "t/vkm"),
    "Electricity": ("intensity_electricity", "TJ/vkm"),
    "Chemicals nec": ("intensity_hydrogen", "t/vkm"),
}


def main() -> None:
    out_rows: list[dict] = []
    for year, path in FILES.items():
        z = pd.read_excel(path, sheet_name="z")
        prov = f"FULFILL_MARIO REF_0_{year} (Golinucci et al. 2025, Apache 2.0)"

        # intensities: sum over origin regions per (destination, powertrain, carrier)
        block = z[z["column sector"].isin(CARS) & (z["column level"] == "Activity")]
        grouped = block.groupby(["column region", "column sector", "row sector"])["value"].sum()
        for (region, car, carrier), val in grouped.items():
            coef, unit = CARRIERS[carrier]
            if val > 0:
                out_rows.append(dict(
                    country=region, year=year, powertrain=car, coef=coef,
                    value=f"{val:.6e}", unit=unit,
                    provenance=f"{prov}; z sum over origin regions"))

        # market shares: car activities -> Car mobility, domestic block
        sh = z[(z["column sector"] == "Car mobility")
               & (z["row sector"].isin(CARS))
               & (z["row region"] == z["column region"])]
        for _, r in sh.iterrows():
            out_rows.append(dict(
                country=r["column region"], year=year, powertrain=r["row sector"],
                coef="market_share", value=f"{r['value']:.6f}", unit="share of vkm",
                provenance=f"{prov}; supply share into Car mobility"))
        print(f"{year}: {len(block)} intensity cells, {len(sh)} share rows")

    out = Path(__file__).parent / "data" / "fulfill_car_block.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["country", "year", "powertrain", "coef",
                                          "value", "unit", "provenance"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nscritte {len(out_rows)} righe -> {out}")

    # validation: IT 2020 against the known decode
    it = [r for r in out_rows if r["country"] == "IT" and r["year"] == 2020]
    print("\nIT 2020 check:")
    for r in sorted(it, key=lambda x: (x["powertrain"], x["coef"])):
        print(f"  {r['powertrain']:26} {r['coef']:22} = {r['value']} {r['unit']}")


if __name__ == "__main__":
    main()
