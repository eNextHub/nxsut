"""Who supplies electricity in the ORIGINAL EXIOBASE Hybrid 3.3.18?

The D15 no-op finding was measured on the built v3.2; this probe answers
Lorenzo's challenge directly on the raw base table (before ``aggregate_ee``
and every gen_v3 move): for each per-tech electricity commodity, which
activities supply it, and how much comes from outside the power family.

Run:  unset VIRTUAL_ENV; caffeinate -is \\
      /opt/anaconda3/envs/mario/bin/python nowcast/probe_netting_base.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent

import mario  # noqa: E402

pfile = ROOT / ("paths_personal.yml" if (ROOT / "paths_personal.yml").exists() else "paths.yml")
paths = yaml.safe_load(open(pfile))["USER"]

print("loading the raw EXIOBASE Hybrid 3.3.18 ...", flush=True)
db = mario.parse_from_txt(paths["raw"], table="SUT", mode="flows")
S = db.S
U = db.U
regions = list(db.get_index("Region"))
acts = list(db.get_index("Activity"))
coms = list(db.get_index("Commodity"))
print(f"grid: {len(regions)} x {len(acts)} x {len(coms)}", flush=True)

ele_coms = [c for c in coms if "electricity" in c.lower()]
print(f"\nelectricity commodities ({len(ele_coms)}):")
for c in ele_coms:
    print(f"  {c}")

POWER_HINTS = ("production of electricity", "electricity by", "transmission", "distribution")
EXEMPT_HINTS = ("steam and hot water", "incineration", "biogasification")

sup_by_act: dict[str, float] = {}
for com in ele_coms:
    block = S.xs(com, axis=1, level=2)
    for (reg_a, _lvl, act), row in block.iterrows():
        v = float(row.sum())
        if v > 0:
            sup_by_act[act] = sup_by_act.get(act, 0.0) + v

tot = sum(sup_by_act.values())
print(f"\ntotal ELE supply (all electricity commodities): {tot:,.0f} TJ "
      f"= {tot / 3.6e6:,.0f} TWh")
print("\n--- suppliers (world, TJ) ---")
offdiag_total = 0.0
for act, v in sorted(sup_by_act.items(), key=lambda kv: -kv[1]):
    name = act.lower()
    kind = ("POWER" if any(h in name for h in POWER_HINTS)
            else "EXEMPT" if any(h in name for h in EXEMPT_HINTS)
            else "OFFDIAG")
    if kind == "OFFDIAG":
        offdiag_total += v
    print(f"  {kind:7s} {v:16,.0f}  ({v / tot * 100:6.3f}%)  {act}")

print(f"\nOFF-DIAGONAL total: {offdiag_total:,.0f} TJ = {offdiag_total / 3.6e6:,.1f} TWh "
      f"({offdiag_total / tot * 100:.3f}% of ELE supply)")

# where does the off-diagonal sit, if anywhere: per-region detail of the top
# off-diagonal suppliers
off_acts = [a for a in sup_by_act
            if not any(h in a.lower() for h in POWER_HINTS + EXEMPT_HINTS)]
if off_acts:
    rows = []
    for com in ele_coms:
        block = S.xs(com, axis=1, level=2)
        for (reg_a, _lvl, act), row in block.iterrows():
            if act in off_acts:
                v = float(row.sum())
                if v > 0:
                    rows.append((reg_a, act, com, v))
    det = pd.DataFrame(rows, columns=["region", "activity", "commodity", "s_ele"])
    det.to_csv(ROOT / "nowcast" / "data" / "netting_probe_base.csv", index=False)
    print("\ntop 15 off-diagonal cells:")
    for _, r in det.sort_values("s_ele", ascending=False).head(15).iterrows():
        print(f"  {r.region}  {r.s_ele:14,.0f}  {r.activity[:44]:46s} -> {r.commodity}")
    print("saved nowcast/data/netting_probe_base.csv")
else:
    print("\nno off-diagonal suppliers in the base table.")
