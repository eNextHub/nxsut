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

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
GWP = {"Carbon dioxide, fossil (air - Emiss)": 1.0,
       "CH4 (air - Emiss)": 29.8,
       "N2O (air - Emiss)": 273.0}
# activity -> (output unit, plausibility band for the GHG footprint in
# g/unit, taken from the transport LCA literature). The bands are the
# acceptance test: a physical denomination that lands outside them is not
# usable, whatever the statistics say.
TRANSPORT_ACTS: dict[str, tuple[str, tuple[float, float]]] = {
    "Road freight transport": ("tkm", (30, 250)),
    "Own-account road freight transport": ("tkm", (30, 300)),
    "Road passenger transport": ("pkm", (20, 150)),
    "Rail passenger transport": ("pkm", (10, 150)),
    "Rail freight transport": ("tkm", (5, 100)),
    "Sea and coastal freight transport": ("tkm", (5, 100)),
    "Sea and coastal passenger transport": ("pkm", (50, 800)),
    "Inland water freight transport": ("tkm", (10, 120)),
    "Inland water passenger transport": ("pkm", (50, 800)),
    "Air freight transport": ("tkm", (300, 2500)),
    "Air passenger transport": ("pkm", (60, 400)),
    "Private car transport, gasoline": ("pkm", (80, 250)),
    "Private car transport, diesel": ("pkm", (80, 250)),
    "Private car transport, LPG": ("pkm", (60, 250)),
    "Private car transport, natural gas": ("pkm", (40, 200)),
    "Private car transport, electric": ("pkm", (0, 200)),
    "Private motorcycle transport": ("pkm", (40, 200)),
}


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

    # Structural gate, before any footprint: a negative output means the
    # Leontief inverse has negative entries, which makes every footprint
    # downstream meaningless (and silently plausible-looking for the regions
    # that stay positive). The base table carries ~40 of these; anything far
    # above that is a pipeline defect, not inherited noise.
    print("\n--- tenuta strutturale ---", flush=True)
    Xall = db.X.iloc[:, 0]
    nneg = int((Xall < 0).sum())
    print(f"  {'OK ' if nneg <= 120 else 'ROTTO'} output negativi: {nneg} / {len(Xall)} "
          f"(base EXIOBASE ~40; U min {db.U.values.min():.3g})", flush=True)
    if nneg > 120:
        worst = Xall[Xall < 0].sort_values().head(5)
        for k, v in worst.items():
            print(f"      {k[0]} {str(k[2])[:46]:48} {v:,.0f}", flush=True)

    print("\n--- footprint GHG AR6 [g/unit] + banda di plausibilita' ---", flush=True)
    db.calc_ghg(profile="exiobase_hybrid")
    f = db.f
    X = db.X.iloc[:, 0]
    lvl0 = db.X.index.get_level_values(0)
    lvl2 = db.X.index.get_level_values(2)
    fails = []
    regions = list(db.get_index("Region"))
    for a, (unit, (lo, hi)) in TRANSPORT_ACTS.items():
        if a not in acts:
            continue
        # world average weighted by output, over EVERY producing region —
        # a six-country sample hides exactly the regions that break
        pairs = []
        for reg in regions:
            try:
                v = float(f.loc["GHG AR6 GWP-100", (reg, "Activity", a)])
            except Exception:
                continue
            x = float(X[(lvl0 == reg) & (lvl2 == a)].sum())
            if x > 0 and np.isfinite(v):
                pairs.append((v, x))
        if not pairs:
            print(f"  ----- {a[:38]:40} nessuna regione produttrice", flush=True)
            continue
        tot = sum(x for _, x in pairs)
        wavg = sum(v * x for v, x in pairs) / tot
        vs = np.array(sorted(v for v, _ in pairs))
        n_out = sum(1 for v, _ in pairs if not (lo <= v <= hi))
        ok = lo <= wavg <= hi
        if not ok:
            fails.append((a, round(wavg, 1), (lo, hi)))
        vals = " ".join(f"{r}={float(f.loc['GHG AR6 GWP-100', (r, 'Activity', a)]):5.0f}"
                        for r in ("IT", "DE", "FR", "US", "CN")
                        if (r, "Activity", a) in f.columns)
        print(f"  {'OK ' if ok else 'FUORI'} {a[:36]:38} {wavg:8.1f} g/{unit:4} "
              f"[{lo}-{hi}]  p10/p50/p90 {np.percentile(vs, 10):7.0f}/"
              f"{np.percentile(vs, 50):7.0f}/{np.percentile(vs, 90):7.0f}  "
              f"fuori {n_out}/{len(pairs)}  {vals}", flush=True)
    print(f"\nfuori banda: {fails if fails else 'nessuno'}", flush=True)

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
    for a in TRANSPORT_ACTS:
        if a in acts:
            print(f"  {a[:42]:44} X mondo = {float(X[lvl2 == a].sum()):>14,.0f}", flush=True)


if __name__ == "__main__":
    main()
