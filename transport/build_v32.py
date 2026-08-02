"""Headless v3.2 build with a negativity report after every stage.

Mirrors gen_v3.ipynb cell by cell (the notebook stays the canonical
pipeline; this runs its cells with streaming output, which nbconvert does
not give). Use it when a build has to be watched or bisected.

    unset VIRTUAL_ENV; caffeinate -is \\
        /opt/anaconda3/envs/mario/bin/python transport/build_v32.py [year] [version]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def report(tag: str, db, scenario: str | None = None) -> None:
    """Negative outputs are the canary: they mean the Leontief inverse has
    gone non-monotone and every footprint downstream is meaningless."""
    X = (db.query("X", scenarios=scenario) if scenario else db.X).iloc[:, 0]
    U = db.query("U", scenarios=scenario) if scenario else db.U
    print(f"[{tag:26}] X<0 {int((X < 0).sum()):5d}  U min {U.values.min():11.4g}",
          flush=True)
    worst = X[X < -1e-6].sort_values().head(4)
    for k, v in worst.items():
        print(f"      {k[0]} {str(k[2])[:44]:46} {v:,.0f}", flush=True)


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import warnings

    import yaml

    warnings.filterwarnings("ignore")
    year = int(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NXSUT_YEAR", 2023))
    version = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NXSUT_VERSION", "v3.2")
    pfile = "paths_personal.yml" if os.path.exists("paths_personal.yml") else "paths.yml"
    paths = yaml.safe_load(open(pfile))["USER"]

    import mario
    import pandas as pd

    from support import nxbase_client as nxc

    nxbase_api = paths.get("nxbase_api", nxc.DEFAULT_API)
    cells = {i: "".join(c["source"])
             for i, c in enumerate(json.load(open("gen_v3.ipynb"))["cells"])
             if c["cell_type"] == "code"}
    # one namespace as both globals and locals: with two dicts the notebook
    # cells' comprehensions would not see names assigned by the same cell
    ns: dict = {"mario": mario, "pd": pd, "nxc": nxc, "os": os, "paths": paths,
                "year": year, "nxbase_api": nxbase_api,
                "baci_path": paths.get("baci"), "scenario": "trades"}

    def run(cell: int) -> None:
        exec(compile(cells[cell], f"cell{cell}", "exec"), ns)   # noqa: S102

    print(f"building nxsut {version} for {year}", flush=True)
    db = mario.parse_from_txt(paths["raw"], table="SUT", mode="flows")
    db.meta.source = "EXIOBASE Hybrid 3.3.18"
    db.aggregate("support/aggregate_ee.xlsx", ignore_nan=True)
    nxc.build_add_sectors_master("support/add_sectors/Master_steel_h2.xlsx",
                                 "_steel_master.xlsx", api_url=nxbase_api)
    db.read_add_sectors_excel("_steel_master.xlsx", read_inventories=True)
    db.add_sectors()
    ns["db"] = db
    run(6)
    report("1 base + steel + BFG", db)

    from transport.pipeline import apply_transport_layer
    apply_transport_layer(db)
    report("2 transport layer", db)

    snapshot = "support/_nxbase_ember_snapshot.csv"
    nxc.get_supply_mix_snapshot(nxbase_api, years=(year,)).to_csv(snapshot, index=False)
    db.update_supply_mix("electricity", scenario="baseline", year=year,
                         ember_path=snapshot)
    report("3 supply mix electricity", db)

    regions = ns["regions"] = list(db.get_index("Region"))
    steel_supply = nxc.get_steel_supply_mix(nxbase_api, year, regions=regions)
    db.update_supply_mix(steel_supply, level="Activity",
                         commodities=[nxc.STEEL_COMMODITY], scenario="baseline",
                         rescale=True)
    report("4 supply mix steel", db)

    db.pool_trade(["Electricity", nxc.STEEL_COMMODITY, nxc.ALUMINIUM_COMMODITY],
                  supply_suffix=" supply", need_suffix=" need")
    report("5 pool_trade", db)

    run(15)
    report("6 trade mix", db, scenario="trades")

    out = os.path.join(paths["export"], version, str(year))
    os.makedirs(out, exist_ok=True)
    db.to_txt(path=out, scenario="trades")
    print(f"esportata -> {out}", flush=True)


if __name__ == "__main__":
    main()
