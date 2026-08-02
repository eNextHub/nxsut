"""Acceptance checks for the first integrated vintage (v3.2).

Reads the exported table and verifies that the pipeline landed everything:
the transport layer (Move B children, private mobility, own-account), the
steel/H2 routes, the pooled commodities, and the electricity anchor that
regresses against the known nxsut values (IT "Electricity need" ~100
gCO2eq/kWh in v3.0 — the UNSD-first supply mix should move it only
slightly, since IT is a UNSD-selected country whose mix matched EMBER to
TVD 0.004).

Run:  unset VIRTUAL_ENV; caffeinate -is \\
      /opt/anaconda3/envs/mario/bin/python transport/validate_v32.py [year] [version]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GWP = {"Carbon dioxide, fossil (air - Emiss)": 1.0,
       "CH4 (air - Emiss)": 29.8,
       "N2O (air - Emiss)": 273.0}
TRANSPORT_ACTS = [
    "Road freight transport", "Road passenger transport",
    "Rail passenger transport", "Rail freight transport",
    "Private car transport, gasoline", "Private car transport, diesel",
    "Private car transport, LPG", "Private car transport, natural gas",
    "Private car transport, electric", "Private motorcycle transport",
    "Own-account road freight transport",
]


def main() -> None:
    import mario  # noqa: PLC0415

    year = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NXSUT_YEAR", "2023")
    version = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NXSUT_VERSION", "v3.2")
    pfile = ROOT / ("paths_personal.yml" if (ROOT / "paths_personal.yml").exists()
                    else "paths.yml")
    paths = yaml.safe_load(open(pfile))["USER"]
    path = os.path.join(paths["export"], version, str(year), "flows")

    print(f"loading {version}/{year}…", flush=True)
    db = mario.parse_from_txt(path, table="SUT", mode="flows")
    acts = list(db.get_index("Activity"))
    coms = list(db.get_index("Commodity"))
    print(f"griglia: {len(db.get_index('Region'))} regioni, {len(acts)} activity, "
          f"{len(coms)} commodity", flush=True)

    print("\n--- presenza settori attesi ---", flush=True)
    for a in TRANSPORT_ACTS:
        print(f"  {'OK ' if a in acts else 'MANCA'} {a}", flush=True)
    pooled = [c for c in coms if c.endswith(" need") or c.endswith(" supply")]
    routes = [a for a in acts if "route" in a.lower() or "BF-BOF" in a or "EAF" in a]
    print(f"  pooled commodities: {len(pooled)} {pooled[:6]}", flush=True)
    print(f"  route/steel activities: {len(routes)}", flush=True)

    print("\n--- footprint GHG AR6 [g/unit] ---", flush=True)
    db.calc_ghg(profile="exiobase_hybrid")
    f = db.f
    X = db.X.iloc[:, 0]
    for a in TRANSPORT_ACTS:
        if a not in acts:
            continue
        vals = []
        for reg in ("IT", "DE", "PL"):
            key = (reg, "Activity", a)
            try:
                vals.append(f"{reg}={float(f.loc['GHG AR6 GWP-100', key]):7.1f}")
            except Exception:
                vals.append(f"{reg}=n/a")
        print(f"  {a[:42]:44} {'  '.join(vals)}", flush=True)

    print("\n--- ancora elettrica (regressione vs v3.0) ---", flush=True)
    for name in ("Electricity need", "Electricity"):
        if name in coms:
            for reg in ("IT", "DE", "FR", "PL"):
                key = (reg, "Commodity", name)
                try:
                    tj = float(f.loc["GHG AR6 GWP-100", key])
                    print(f"  {name} {reg}: {tj:8.2f} tCO2eq/TJ "
                          f"({tj * 3.6 / 1000 * 1000:6.1f} gCO2eq/kWh)", flush=True)
                except Exception:
                    pass
            break

    print("\n--- output trasporto (vs statistiche) ---", flush=True)
    lvl2 = db.X.index.get_level_values(2)
    for a in TRANSPORT_ACTS:
        if a in acts:
            print(f"  {a[:42]:44} X mondo = {float(X[lvl2 == a].sum()):>14,.0f}", flush=True)


if __name__ == "__main__":
    main()
