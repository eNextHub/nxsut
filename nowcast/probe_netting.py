"""Measure the off-diagonal electricity supply in the v3.2 table (D9 probe)."""

import os
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path("/Users/lorenzorinaldi/Documents/GitHub/eNextHub/nxsut")
sys.path.insert(0, str(ROOT))

import mario  # noqa: E402

paths = yaml.safe_load(open(ROOT / "paths_personal.yml"))["USER"]
path = os.path.join(paths["export"], "v3.2", "2023", "flows")
print("loading v3.2/2023 ...", flush=True)
db = mario.parse_from_txt(path, table="SUT", mode="flows")

S = db.S  # activities x commodities (flows)
U = db.U  # commodities x activities
regions = list(db.get_index("Region"))
acts = list(db.get_index("Activity"))
print(f"grid: {len(regions)} x {len(acts)}", flush=True)

ELE = "Electricity"
ELE_NEED = "Electricity need"

# who supplies Electricity, summed across regions
sup = S.xs(ELE, axis=1, level=2)  # index (region, level, activity), cols regions? -> squeeze
# S columns are (Region, Level, Item); xs on item leaves (Region) col level
sup_by_act = {}
for (reg_a, _lvl, act), row in sup.iterrows():
    v = row.sum()  # supply of ELE by this (region, activity) to any region (should be own region)
    if v > 0:
        sup_by_act.setdefault(act, 0.0)
        sup_by_act[act] += v

tot = sum(sup_by_act.values())
print(f"\ntotal ELE supply: {tot:,.0f} TJ = {tot / 3.6e6:,.0f} TWh")
print("\n--- suppliers of Electricity (world, TJ) ---")
for act, v in sorted(sup_by_act.items(), key=lambda kv: -kv[1]):
    print(f"  {v:16,.0f}  ({v / tot * 100:5.2f}%)  {act}")

# off-diagonal candidates = non power-family suppliers; measure own-use cap
POWER_PREFIX = "Production of electricity"
EXEMPT_HINTS = ("Electricity supply", "Steam and hot water", "incineration",
                "Blast furnace gas", "Oxygen steel furnace gas")
offdiag = [a for a in sup_by_act
           if not a.startswith(POWER_PREFIX) and not any(h in a for h in EXEMPT_HINTS)]
print(f"\n--- off-diagonal (nettable candidates): {len(offdiag)} activities ---")
rows = []
for reg in regions:
    for act in offdiag:
        try:
            s_val = S.loc[(reg, "Activity", act), (reg, "Commodity", ELE)]
        except KeyError:
            continue
        if s_val <= 0:
            continue
        try:
            u_val = U.loc[(reg, "Commodity", ELE_NEED), (reg, "Activity", act)]
        except KeyError:
            u_val = 0.0
        rows.append((reg, act, float(s_val), float(u_val)))

df = pd.DataFrame(rows, columns=["region", "activity", "s_ele", "u_need"])
df["net"] = df[["s_ele", "u_need"]].min(axis=1)
df["residual"] = df["s_ele"] - df["net"]
print(f"cells with off-diag ELE supply: {len(df)}")
print(f"off-diag supply total: {df.s_ele.sum():,.0f} TJ = {df.s_ele.sum() / 3.6e6:,.1f} TWh "
      f"({df.s_ele.sum() / tot * 100:.2f}% of world ELE supply)")
print(f"nettable (capped at own use): {df.net.sum():,.0f} TJ = {df.net.sum() / 3.6e6:,.1f} TWh")
print(f"residual (supply beyond own use): {df.residual.sum():,.0f} TJ")

print("\n--- top 15 regions by off-diag supply (TJ, % of region ELE supply) ---")
reg_tot = {}
for reg in regions:
    try:
        col = S.xs((reg, "Commodity", ELE), axis=1)
        reg_tot[reg] = float(col.sum().sum())
    except KeyError:
        reg_tot[reg] = float("nan")
g = df.groupby("region")[["s_ele", "net", "residual"]].sum().sort_values("s_ele", ascending=False)
for reg, r in g.head(15).iterrows():
    share = r.s_ele / reg_tot.get(reg, float("nan")) * 100
    print(f"  {reg}: {r.s_ele:12,.0f}  ({share:5.2f}%)  net {r.net:12,.0f}  resid {r.residual:10,.0f}")

print("\n--- top 15 off-diag activities (world, TJ) ---")
ga = df.groupby("activity")[["s_ele", "net", "residual"]].sum().sort_values("s_ele", ascending=False)
for act, r in ga.head(15).iterrows():
    print(f"  {r.s_ele:14,.0f}  net {r.net:14,.0f}  {act}")

df.to_csv(ROOT / "nowcast" / "data" / "netting_probe.csv", index=False)
print("\nsaved netting_probe.csv")
