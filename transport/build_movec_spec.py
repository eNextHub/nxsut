"""Move C, stage 1 — own-account road freight: per-region spec.

Assembles what the extraction needs, inspectable before any surgery:

- **own-account tkm** per region, Y11: ITF ``frt.own`` observed; fallback =
  hire tkm × the EU-observed own/(1−own) ratio (own = 15.4% of total tkm,
  road_go_ta_tg 2011 — declared);
- **own load factor** per country (leg-1 observed ``load_factor_own``,
  default 7.2 tkm/vkm) and the NXTR HGV intensity → fuel demand;
- the **sector propensity table** (relative weights): seeded by the
  OBSERVED own-account share per NST2007 goods group (ESTAT.ROADGOODS —
  removals 44%, waste 28%, construction minerals 19%, agri-food ~18%,
  metals 9.6%, chemicals 8.4%, transport equipment 5.9%) and **dampened
  where a sector's diesel is dominated by off-road machinery** (mining
  haul trucks, farm tractors, construction equipment): the allocation
  base at apply time is diesel_S × propensity_S, and off-road diesel must
  stay in the sectors (UNSD keeps it in the industry rows too — the
  perimeter self-preserves only if the propensity encodes it). Judgment
  layer, declared per class, bounded by the observed regional total and
  the per-cell caps; the dry-run prints the resulting allocation for
  eyeballing before the write.

Output: ``transport/data/movec_spec.csv`` (region rows: own_tkm, tier,
load_own) + ``transport/data/movec_propensity.csv`` (sector -> weight).
"""

from __future__ import annotations

import csv
import io
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
API = "http://127.0.0.1:8000"

EXIOBASE_REGIONS = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK", "GB", "NO", "CH", "TR", "RU", "CN", "US", "JP", "IN",
    "CA", "KR", "BR", "MX", "AU", "ID", "ZA", "TW",
    "WA", "WE", "WF", "WL", "WM",
]
OWN_SHARE_EU = 0.154          # observed, road_go_ta_tg 2011
LOAD_OWN_DEFAULT = 7.2        # tkm/vkm, leg-1 EU pattern
INT_HGV = 2.7e-4              # t diesel per vkm (NXTR v0)

# sector propensity classes (relative weights; 0 = never extracted).
# Seeded by observed NST own-shares, dampened where diesel is off-road.
PROPENSITY_RULES: list[tuple[float, list[str], str]] = [
    (1.0, ["Retail trade", "Wholesale trade", "Sale, maintenance, repair of motor",
           "Retail sale of automotive fuel"],
     "trade/distribution: fleet-dominated diesel (GT04/GT18 distribution)"),
    (0.8, ["Processing of", "Production of meat", "Manufacture of beverages",
           "Manufacture of fish products", "Manufacture of tobacco",
           "Sugar refining", "Processed rice"],
     "food industry: GT04 own 17.7% + distribution fleets"),
    (0.7, ["Incineration of waste", "Landfill of waste", "Recycling of",
           "Re-processing of", "Biogasification of", "Composting of",
           "Waste water treatment", "Manure treatment"],
     "waste/recycling: GT14 own 28%, collection fleets (plant use dampens)"),
    (0.6, ["Construction"],
     "construction: GT09 own 18.8%, dampened for off-road equipment"),
    (0.5, ["Manufacture of bricks", "Manufacture of cement",
           "Manufacture of ceramic goods", "Manufacture of glass"],
     "construction materials: GT09"),
    (0.4, ["Manufacture of wood", "Paper", "Pulp", "Publishing",
           "Manufacture of furniture", "Manufacture of textiles",
           "Manufacture of wearing apparel", "Tanning and dressing"],
     "light manufacturing: GT05/GT06/GT13"),
    (0.3, ["Manufacture of machinery", "Manufacture of fabricated metal",
           "Manufacture of electrical machinery", "Manufacture of office machinery",
           "Manufacture of radio", "Manufacture of medical", "Hotels and restaurants"],
     "equipment manufacturing + horeca supply: GT11"),
    (0.2, ["Cultivation of", "farming", "Raw milk", "Wool", "Meat animals",
           "Animal products", "Forestry", "Fishing"],
     "agriculture: GT01 own 17.6% but tractor diesel dominates -> dampened"),
    (0.0, ["Manufacture of basic iron", "Aluminium production", "Copper production",
            "Lead, zinc and tin production", "Precious metals production",
            "Other non-ferrous metal production", "Casting of metals",
            "Chemicals nec", "Plastics, basic", "N-fertiliser",
            "P- and other fertiliser", "Petroleum Refinery",
            "Manufacture of coke oven products", "Manufacture of rubber",
            "Manufacture of other non-metallic mineral",
            "Manufacture of motor vehicles", "Manufacture of other transport equipment"],
     "heavy/process industry OUT of the pool: bulk diesel cells are feedstock/process (PL Chemicals 2.4 Mt), never fleet"),
    (0.1, ["Mining of", "Quarrying of", "Extraction"],
     "mining: GT03 own 26% of road tkm BUT haul-truck diesel is off-road"),
]


def fetch_api(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def main() -> None:
    # own + hire tkm Y11 from ITF (API)
    tkm: dict[tuple[str, str], float] = defaultdict(float)
    for act, kind in [("Road freight transport - own account", "own"),
                      ("Road freight transport - hire and reward", "hire"),
                      ("Road freight transport (total)", "total")]:
        for r in fetch_api({"parameter": "Total output",
                            "source": "International Transport Forum",
                            "activity": act, "limit": "100000"}):
            parts = r["item_1"].split("-")
            if len(parts) == 4 and parts[3] == "Y11":
                tkm[(kind, parts[2])] += float(r["value"])

    # observed own load factors (leg 1)
    load: dict[str, float] = {}
    with open(HERE / "data" / "derived_recipes_v0.csv") as f:
        for r in csv.DictReader(f):
            if r["tech"] == "HGV" and r["coef"] == "load_factor_own" and r["year"] == "Y11":
                load[r["country"]] = float(r["value"])

    rows_out: list[dict] = []
    n_obs = 0
    for region in EXIOBASE_REGIONS:
        own = tkm.get(("own", region), 0.0)
        if own > 0:
            tier = "ITF-observed"
            n_obs += 1
        else:
            hire = tkm.get(("hire", region), 0.0) or tkm.get(("total", region), 0.0) * (1 - OWN_SHARE_EU)
            own = hire * OWN_SHARE_EU / (1 - OWN_SHARE_EU)
            tier = "EU-share-fallback" if hire > 0 else "apply-side-from-B-child"
        rows_out.append(dict(region=region, own_tkm=round(own, 1), tier=tier,
                             load_own=load.get(region, LOAD_OWN_DEFAULT),
                             int_hgv=INT_HGV))
    with open(HERE / "data" / "movec_spec.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "own_tkm", "tier", "load_own", "int_hgv"])
        w.writeheader()
        w.writerows(rows_out)

    with open(HERE / "data" / "movec_propensity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["weight", "pattern", "rationale"])
        w.writeheader()
        for weight, patterns, why in PROPENSITY_RULES:
            for pat in patterns:
                w.writerow(dict(weight=weight, pattern=pat, rationale=why))

    print(f"{len(rows_out)} regioni ({n_obs} own-tkm ITF osservate) -> movec_spec.csv")
    print(f"{sum(len(p) for _, p, _ in PROPENSITY_RULES)} pattern propensita -> movec_propensity.csv")
    for r in rows_out:
        if r["region"] in ("IT", "DE", "PL", "US", "WA"):
            print(f"  {r['region']}: own={r['own_tkm']:,.0f} Mtkm ({r['tier']}), "
                  f"load={r['load_own']}")


if __name__ == "__main__":
    main()
