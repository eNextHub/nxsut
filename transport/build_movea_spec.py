"""Move A, stage 1 — assemble the private-mobility spec per EXIOBASE region.

Move A adds household-operated car (+moto) activities producing a private
road-mobility service commodity (the FULFILL MIMO pattern) and reroutes
the households' motor-fuel purchases from Y into their use columns. This
builder assembles everything the apply script needs, per region, with
tier and provenance per cell — inspectable before the surgery:

- **tech shares** (share of car vkm): carpark stock shares from the NXTR
  master's ``mkt`` sheet (``data/nxtr_master.xlsx``), period **Y13 as the
  2011 proxy** (the carpark series starts in 2013; fleet inertia,
  declared). Regions outside the carpark: median of the observed shares.
- **intensities** (native hybrid units per vkm): FULFILL 2011 per country
  (EU-27, ``data/fulfill_car_block.csv``); elsewhere the FULFILL-2011
  median per powertrain (declared default). MOTO: the NXTR default.
- **activity**: observed car pkm (ESTAT preferred, ITF fallback — the
  plausibility rule) and moto pkm (ESTAT), year 2011; regions without
  observed pkm are flagged ``synth`` — the apply script synthesises vkm
  from the households' gasoline purchases (gasoline-anchor inversion,
  declared).
- **occupancy**: NXTR v0 defaults (cars 1.5, moto 1.1 pkm/vkm).

Output: ``transport/data/movea_spec.csv``
(region, tech, share, intensity, intensity_unit, carrier, occupancy,
pkm_obs, tier, provenance).
"""

from __future__ import annotations

import csv
import io
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
API = "http://127.0.0.1:8000"

EXIOBASE_REGIONS = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK", "GB", "NO", "CH", "TR", "RU", "CN", "US", "JP", "IN",
    "CA", "KR", "BR", "MX", "AU", "ID", "ZA", "TW",
    "WA", "WE", "WF", "WL", "WM",
]
CAR_TECHS = ["CAR.G", "CAR.D", "CAR.LPG", "CAR.CNG", "CAR.E"]
# tech -> (carrier commodity concept, FULFILL coef, intensity unit)
CARRIER = {
    "CAR.G": ("GASO", "intensity_liquid", "t/vkm"),
    "CAR.D": ("DIES", "intensity_liquid", "t/vkm"),
    "CAR.LPG": ("LPG", "intensity_lpg", "t/vkm"),
    "CAR.CNG": ("NGAS", "intensity_gas", "t/vkm"),
    "CAR.E": ("ELE", "intensity_electricity", "TJ/vkm"),
    "MOTO": ("GASO", None, "t/vkm"),
}
MOTO_INT = 3.0e-5          # NXTR v0 default, t/vkm
OCC = {"car": 1.5, "moto": 1.1}
PKM_SOURCES = {
    "car": [("Eurostat road passenger performance (pkm)",
             "Road passenger transport - cars"),
            ("International Transport Forum",
             "Road passenger transport - cars")],
    "moto": [("Eurostat road passenger performance (pkm)",
              "Road passenger transport - motorcycles and mopeds")],
}


def fetch_api(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def main() -> None:
    # --- tech shares from the NXTR master mkt sheet (Y13 proxy) ---
    mkt = pd.read_excel(HERE / "data" / "nxtr_master.xlsx", sheet_name="mkt")
    y13 = mkt[mkt["period"] == "Y13"]
    shares_obs: dict[str, dict[str, float]] = defaultdict(dict)
    for _, r in y13.iterrows():
        shares_obs[r["site"]][r["tech"]] = float(r["value"])
    medians = {t: statistics.median([s[t] for s in shares_obs.values() if t in s])
               for t in CAR_TECHS}
    norm = sum(medians.values())
    medians = {t: v / norm for t, v in medians.items()}
    print(f"share parco: {len(shares_obs)} paesi osservati (Y13); "
          f"mediana: { {t: round(v, 3) for t, v in medians.items()} }")

    # --- FULFILL 2011 intensities per country + medians ---
    ints: dict[tuple[str, str], float] = {}
    by_coef: dict[str, list[float]] = defaultdict(list)
    with open(HERE / "data" / "fulfill_car_block.csv") as f:
        for r in csv.DictReader(f):
            if r["year"] == "2011" and r["coef"].startswith("intensity"):
                ints[(r["country"], r["coef"])] = float(r["value"])
                by_coef[r["coef"]].append(float(r["value"]))
    int_median = {c: statistics.median(v) for c, v in by_coef.items()}
    print(f"intensita FULFILL 2011: {len({k[0] for k in ints})} paesi; mediane: "
          f"{ {c: f'{v:.3e}' for c, v in int_median.items()} }")

    # --- observed pkm (cars, moto) Y11: first source with data wins ---
    by_src: dict[tuple[str, str, str], float] = defaultdict(float)
    for kind, specs in PKM_SOURCES.items():
        for src, act in specs:
            for r in fetch_api({"parameter": "Total output", "source": src,
                                "activity": act, "limit": "100000"}):
                parts = r["item_1"].split("-")
                if len(parts) == 4 and parts[3] == "Y11":
                    by_src[(kind, src, parts[2])] += float(r["value"])
    pkm: dict[tuple[str, str], float] = {}
    for kind, specs in PKM_SOURCES.items():
        for region in EXIOBASE_REGIONS:
            for src, _ in specs:
                q = by_src.get((kind, src, region), 0.0)
                if q > 0:
                    pkm[(kind, region)] = q
                    break

    rows_out: list[dict] = []
    for region in EXIOBASE_REGIONS:
        sh = shares_obs.get(region)
        tier_sh = "carpark-Y13" if sh else "median"
        if not sh:
            sh = medians
        tot = sum(sh.get(t, 0.0) for t in CAR_TECHS)
        car_pkm = pkm.get(("car", region), 0.0)
        moto_pkm = pkm.get(("moto", region), 0.0)
        for t in CAR_TECHS:
            carrier, coef, unit = CARRIER[t]
            val = ints.get((region, coef))
            tier_i = "FULFILL-2011" if val is not None else "FULFILL-median"
            if val is None:
                val = int_median.get(coef, 0.0)
            rows_out.append(dict(
                region=region, tech=t, share=round(sh.get(t, 0.0) / tot, 4),
                intensity=f"{val:.6e}", intensity_unit=unit, carrier=carrier,
                occupancy=OCC["car"], pkm_obs=round(car_pkm, 1),
                tier=f"sh:{tier_sh}|int:{tier_i}|pkm:"
                     + ("obs" if car_pkm > 0 else "synth"),
                provenance="shares: ESTAT.CARPARK stock Y13 as 2011 proxy (or "
                           "observed median); intensity: FULFILL REF 2011 (or "
                           "median); pkm: ESTAT/ITF Y11 (or gasoline-anchor "
                           "synthesis at apply time)"))
        rows_out.append(dict(
            region=region, tech="MOTO", share=1.0, intensity=f"{MOTO_INT:.6e}",
            intensity_unit="t/vkm", carrier="GASO", occupancy=OCC["moto"],
            pkm_obs=round(moto_pkm, 1),
            tier="int:NXTR-default|pkm:" + ("obs" if moto_pkm > 0 else "none"),
            provenance="MOTO: NXTR v0 default intensity; pkm ESTAT Y11 where "
                       "observed, else the region gets a zero-output MOTO "
                       "activity (declared)"))

    out = HERE / "data" / "movea_spec.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    n_obs = len({r["region"] for r in rows_out if "pkm:obs" in r["tier"]})
    print(f"\n{len(rows_out)} righe spec, {len(EXIOBASE_REGIONS)} regioni "
          f"({n_obs} con pkm auto osservate) -> {out}")
    for region in ("IT", "US", "WA"):
        sel = [r for r in rows_out if r["region"] == region and r["tech"] != "MOTO"]
        line = "  ".join(f"{r['tech']}={r['share']}" for r in sel)
        pk = sel[0]["pkm_obs"] if sel else "-"
        print(f"  {region}: {line}  pkm_auto={pk}")


if __name__ == "__main__":
    main()
