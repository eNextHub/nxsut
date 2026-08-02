"""Move B (c), stage 2b — write the split into the table (add_sectors + surgery).

The write pass of the deterministic split validated by stage 2a:

1. **Register** the four children in the grid via MARIO's standard
   inventory path (`read_add_sectors_excel` + `add_sectors()`) with a
   register-only template generated from the blastfurnacegas.xlsx base
   (Master rows swapped, empty inventory sheets, DB-units extended) —
   NOT the `split=True`/cvxlab path (IOT-only machinery; decision
   2026-08-02: deterministic, MARIO untouched).
2. **Surgery** (the BFG idiom): per region, overwrite the children's
   coefficient columns (u/v/e = parent absolutes x shares ÷ child output)
   and the child-commodity rows (use rule + IPF, physical units), zero
   the parent, `update_scenarios('baseline', z, v, e, Y)` +
   `reset_to_coefficients`.
3. **Re-denomination**: child outputs are physical — X = Q (Mtkm/Mpkm)
   observed; where Q is unobserved it is synthesised as M ÷ median
   table-implied price of the child type (from the stage-2a dry-run CSV;
   the grid needs uniform units per commodity — declared per region).
   Rail/road children only; pipelines are already their own MEUR sector.
4. **Checks**: parent output gone, children alive, per-region commodity
   balance (supply == use) on the children, IT spot values; then
   `to_txt` export of the split baseline for inspection/reload.

Run:  unset VIRTUAL_ENV; caffeinate -is \
      /opt/anaconda3/envs/mario/bin/python transport/apply_moveb_split_write.py
"""

from __future__ import annotations

import csv
import shutil
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent

PARENTS = {
    "road_pipe": ("Other land transport", "Other land transportation services"),
    "rail": ("Transport via railways", "Railway transportation services"),
    "sea": ("Sea and coastal water transport",
            "Sea and coastal water transportation services"),
    "iww": ("Inland water transport", "Inland water transportation services"),
    "air": ("Air transport (62)", "Air transport services (62)"),
}
# child key -> (activity name, commodity name, unit, inventory sheet)
CHILD_DEF = {
    "ROAD.FRT": ("Road freight transport", "Road freight transport services", "Mtkm", "RFT"),
    "ROAD.PAX": ("Road passenger transport", "Road passenger transport services", "Mpkm", "RPX"),
    "TRN.P": ("Rail passenger transport", "Rail passenger transport services", "Mpkm", "RLP"),
    "TRN.F": ("Rail freight transport", "Rail freight transport services", "Mtkm", "RLF"),
    "SEA.FRT": ("Sea and coastal freight transport",
                "Sea and coastal freight transport services", "Mtkm", "SEF"),
    "SEA.PAX": ("Sea and coastal passenger transport",
                "Sea and coastal passenger transport services", "Meuro", "SEP"),
    "IWW.FRT": ("Inland water freight transport",
                "Inland water freight transport services", "Mtkm", "IWF"),
    "IWW.PAX": ("Inland water passenger transport",
                "Inland water passenger transport services", "Meuro", "IWP"),
    "AIR.FRT": ("Air freight transport", "Air freight transport services",
                "Mtkm", "AIF"),
    "AIR.PAX": ("Air passenger transport", "Air passenger transport services",
                "Meuro", "AIP"),
}
CHILDREN = {"road_pipe": ["ROAD.FRT", "ROAD.PAX"], "rail": ["TRN.P", "TRN.F"],
    "sea": ["SEA.FRT", "SEA.PAX"], "iww": ["IWW.FRT", "IWW.PAX"],
    "air": ["AIR.FRT", "AIR.PAX"],
}
# no open pkm exists for these: they keep the monetary denomination
MONETARY_CHILDREN = {"SEA.PAX", "IWW.PAX", "AIR.PAX"}
FUEL_NAMES = [
    "Motor Gasoline", "Gas/Diesel Oil", "Liquefied Petroleum Gases (LPG)",
    "Biogasoline", "Biodiesels", "Other Liquid Biofuels", "Kerosene",
    "Heavy Fuel Oil", "Natural Gas Liquids",
]
TEMPLATE_BASE = ROOT / "support" / "add_sectors" / "blastfurnacegas.xlsx"
TEMPLATE_OUT = HERE / "out" / "_moveb_add_sectors.xlsx"
EXPORT_DIR = HERE / "out" / "_moveb_split_table"


def load_spec() -> dict:
    spec: dict = defaultdict(dict)
    with open(HERE / "data" / "moveb_split_spec.csv") as f:
        for r in csv.DictReader(f):
            if r["child"] == "PIPE":
                continue
            spec[(r["region"], r["block"], r["row_class"])][r["child"]] = float(r["share"])
    for (_, _, row_class), shares in spec.items():
        if row_class in ("other", "fuel_liquid"):
            tot = sum(shares.values())
            if tot > 0:
                for c in shares:
                    shares[c] /= tot
    return spec


def median_prices() -> dict[str, float]:
    """Median table-implied price per child (stage-2a dry-run) — the
    synthesiser for regions without observed Q."""
    vals: dict[str, list[float]] = defaultdict(list)
    with open(HERE / "data" / "moveb_split_dryrun.csv") as f:
        for r in csv.DictReader(f):
            if r["implied_price"]:
                vals[r["child"]].append(float(r["implied_price"]))
    return {c: statistics.median(v) for c, v in vals.items()}


def ipf(seed: np.ndarray, rt: np.ndarray, ct: np.ndarray, iters: int = 30) -> np.ndarray:
    a = np.array(seed, dtype=float)
    for _ in range(iters):
        rs = a.sum(axis=1)
        nz = rs > 0
        a[nz] *= (rt[nz] / rs[nz])[:, None]
        cs = a.sum(axis=0)
        nz = cs > 0
        a[:, nz] *= ct[nz] / cs[nz]
    return a


def build_template(regions: list[str]) -> None:
    import openpyxl

    shutil.copy(TEMPLATE_BASE, TEMPLATE_OUT)
    wb = openpyxl.load_workbook(TEMPLATE_OUT)
    ws = wb["Master"]
    ws.delete_rows(2, ws.max_row - 1)
    for i, (act, com, unit, sheet) in enumerate(CHILD_DEF.values(), start=2):
        for j, val in enumerate(["GLOBAL", act, com, sheet, 1, unit, 1, None], start=1):
            ws.cell(row=i, column=j, value=val)
    for old in ("BFG", "O2G"):
        del wb[old]
    for _, (_, _, _, sheet) in CHILD_DEF.items():
        s = wb.create_sheet(sheet)
        for j, h in enumerate(["Quantity", "Unit", "Input", "Item type", "DB Item",
                               "DB Region", "Change type", "Source"], start=1):
            s.cell(row=1, column=j, value=h)
    units = wb["DB units"]
    row = units.max_row + 1
    for act, com, unit, _ in CHILD_DEF.values():
        units.cell(row=row, column=1, value="Activity")
        units.cell(row=row, column=2, value=act)
        units.cell(row=row, column=3, value="None")
        units.cell(row=row + 1, column=1, value="Commodity")
        units.cell(row=row + 1, column=2, value=com)
        units.cell(row=row + 1, column=3, value=unit)
        row += 2
    wb.save(TEMPLATE_OUT)
    print(f"template register-only -> {TEMPLATE_OUT}", flush=True)


def apply(db) -> None:
    """Move B on an already-loaded db, in place — the pipeline entry point."""
    regions = list(db.get_index("Region"))

    build_template(regions)
    db.read_add_sectors_excel(str(TEMPLATE_OUT), read_inventories=True)
    db.add_sectors()
    print("children registrati:", list(db.new_activities), flush=True)

    spec = load_spec()
    prices = median_prices()
    print("prezzi mediani (sintesi Q mancanti):",
          {k: round(v, 3) for k, v in prices.items()}, flush=True)

    U, V, E, S, Y = db.U, db.V, db.E, db.S, db.Y
    X = db.X
    x_series = X.iloc[:, 0] if hasattr(X, "columns") else X  # first col, name-agnostic
    print(f"X shape: {getattr(X, 'shape', '?')}, col: "
          f"{list(getattr(X, 'columns', ['-']))[:2]}", flush=True)
    u, s, v, e = db.u, db.s, db.v, db.e
    coms = list(db.get_index("Commodity"))
    fuels = [c for c in FUEL_NAMES if c in coms]

    # Two-phase surgery: compute everything into dicts (fast read loop),
    # then write in bulk — column assignments on the natural axis, row
    # assignments via ONE transpose round-trip per matrix. Repeated .loc
    # row/scalar writes on the 70M-cell coefficient frames consolidate the
    # whole block per call under pandas-3 CoW (~hours); this path is ~two
    # big copies per matrix.
    synth = 0
    u_cols: dict[tuple, np.ndarray] = {}
    v_cols: dict[tuple, np.ndarray] = {}
    e_cols: dict[tuple, np.ndarray] = {}
    u_rows: dict[tuple, pd.Series] = {}
    y_rows: dict[tuple, np.ndarray] = {}
    s_rows: dict[tuple, pd.Series] = {}

    for i, region in enumerate(regions):
        print(f"  [{i + 1}/{len(regions)}] {region}", flush=True)
        for block, (p_act, p_com) in PARENTS.items():
            children = CHILDREN[block]
            sh_other = spec[(region, block, "other")]
            sh_fuel = spec[(region, block, "fuel_liquid")]
            q_spec = spec.get((region, block, "Q"), {})

            u_col = U[(region, "Activity", p_act)]
            v_col = V[(region, "Activity", p_act)]
            e_col = E[(region, "Activity", p_act)]
            fuel_mask = u_col.index.get_level_values(2).isin(fuels)
            u_row = U.loc[(region, "Commodity", p_com), :]
            y_row = Y.loc[(region, "Commodity", p_com), :]
            users = pd.concat([u_row, y_row])
            M = float(users.sum())

            # transport self-use (subcontracting: the parent buys its own
            # commodity) would land on dead cells (zeroed parent row x
            # zeroed parent column) and vanish at rebuild — handled
            # explicitly as a child->child DIAGONAL block (freight
            # subcontracts freight): monetary self_val x share per child.
            self_col_key = (region, "Activity", p_act)
            self_row_key = (region, "Commodity", p_com)
            self_val = float(u_row[self_col_key])

            Q: dict[str, float] = {}
            for c in children:
                m_child = sh_other.get(c, 0.0) * M
                if c in MONETARY_CHILDREN:      # identity: output stays MEUR
                    Q[c] = m_child
                    continue
                q = q_spec.get(c, 0.0)
                if q <= 0:
                    if m_child > 0 and c not in prices:
                        # no observed Q and no median price to synthesise from:
                        # the dry-run has not been re-run for this child. Refuse
                        # rather than scale a physical unit by a monetary value.
                        raise SystemExit(
                            f"{c}: nessun prezzo mediano (rilancia il dry-run "
                            f"apply_moveb_split.py prima del write)")
                    q = m_child / prices[c] if m_child > 0 else 0.0
                    synth += 1
                Q[c] = q

            pax = next(c for c in children if c.endswith("PAX") or c == "TRN.P")
            frt = next(c for c in children if c.endswith("FRT") or c == "TRN.F")
            users2 = users.drop(self_col_key)          # self allocated apart
            neg = users2.clip(upper=0.0).to_numpy()
            pos = users2.clip(lower=0.0).to_numpy()
            is_final = np.array(
                [(lvl[1] != "Activity" and any(k in str(lvl[2]) for k in
                  ("households", "non-profit", "government")))
                 for lvl in users2.index], dtype=bool)
            rule = np.zeros((len(children), len(users2)))
            rule[children.index(pax), is_final] = pos[is_final]
            rule[children.index(frt), ~is_final] = pos[~is_final]
            shares_vec = np.array([sh_other.get(c, 0.0) for c in children])
            seed = 0.9 * rule + 0.1 * np.outer(shares_vec, pos)
            closed = ipf(seed, shares_vec * pos.sum(), pos) + np.outer(shares_vec, neg)
            # monetary row total per child = sh x (M - self) + sh x self = sh x M

            n_u = len(u_row) - 1                      # users2 U-part length
            u2_index = users2.index[:n_u]
            for k, c in enumerate(children):
                act, com, _, _ = CHILD_DEF[c]
                m_child = sh_other.get(c, 0.0) * M
                xq = Q[c] if Q[c] > 0 else max(m_child, 1e-9)
                col = u_col * sh_other.get(c, 0.0)
                col[fuel_mask] = u_col[fuel_mask] * sh_fuel.get(c, 0.0)
                col[self_row_key] = 0.0               # self handled on the row side
                u_cols[(region, "Activity", act)] = (col / xq).to_numpy()
                v_cols[(region, "Activity", act)] = (v_col * sh_other.get(c, 0.0) / xq).to_numpy()
                e_cols[(region, "Activity", act)] = (e_col * sh_fuel.get(c, 0.0) / xq).to_numpy()
                one_hot = pd.Series(0.0, index=S.columns)
                one_hot[(region, "Commodity", com)] = 1.0
                s_rows[(region, "Activity", act)] = one_hot
                # physical scale: child's own monetary total, not M
                scale = (Q[c] / m_child) if m_child > 0 else 0.0
                phys = closed[k] * scale
                u_flows = pd.Series(0.0, index=u_row.index)
                u_flows[u2_index] = phys[:n_u]
                x_users = x_series.reindex(u_flows.index)
                coeff = (u_flows / x_users.replace(0, np.nan)).fillna(0.0)
                # self diagonal: coeff = physical self flow / X_child = self_val / M
                coeff[(region, "Activity", act)] = self_val / M if M > 0 else 0.0
                u_rows[(region, "Commodity", com)] = coeff
                y_rows[(region, "Commodity", com)] = phys[n_u:]

            zero_col = np.zeros(len(u_col))
            u_cols[(region, "Activity", p_act)] = zero_col
            v_cols[(region, "Activity", p_act)] = np.zeros(len(v_col))
            e_cols[(region, "Activity", p_act)] = np.zeros(len(e_col))
            s_rows[(region, "Activity", p_act)] = pd.Series(0.0, index=S.columns)
            u_rows[(region, "Commodity", p_com)] = pd.Series(0.0, index=u_row.index)
            y_rows[(region, "Commodity", p_com)] = np.zeros(len(y_row))

    print(f"calcolo completato (Q sintetizzate: {synth}); write bulk…", flush=True)

    # columns: natural axis, single-shot per matrix
    for key, arr in u_cols.items():
        u[key] = arr
    for key, arr in v_cols.items():
        v[key] = arr
    for key, arr in e_cols.items():
        e[key] = arr
    # rows: one transpose round-trip per matrix
    uT = u.T
    for key, ser in u_rows.items():
        uT[key] = ser.to_numpy()
    u = uT.T
    sT = s.T
    for key, ser in s_rows.items():
        sT[key] = ser.to_numpy()
    s = sT.T
    yT = Y.T
    for key, arr in y_rows.items():
        yT[key] = arr
    Y = yT.T
    print("surgery completata", flush=True)
    z = db.z
    z.update(s)
    z.update(u)
    db.update_scenarios("baseline", z=z, v=v, e=e, Y=Y)
    db.reset_to_coefficients("baseline")

    # --- checks ---
    X2 = db.X
    for block, (p_act, _) in PARENTS.items():
        xp = float(X2.loc[(slice(None), "Activity", p_act), :].to_numpy().sum())
        print(f"parent '{p_act}' output post-split: {xp:.3e} (atteso ~0)", flush=True)
    for c, (act, com, unit, _) in CHILD_DEF.items():
        xc = float(X2.loc[(slice(None), "Activity", act), :].to_numpy().sum())
        print(f"child {c}: X globale = {xc:,.0f} {unit}", flush=True)
    it_frt = float(X2.loc[("IT", "Activity", CHILD_DEF["ROAD.FRT"][0]), :].to_numpy().sum())
    print(f"IT ROAD.FRT output = {it_frt:,.1f} Mtkm (atteso ~ Q osservato)", flush=True)


def main() -> None:
    """Standalone dev run: load the base table, apply Move B, export."""
    pfile = ROOT / ("paths_personal.yml" if (ROOT / "paths_personal.yml").exists()
                    else "paths.yml")
    paths = yaml.safe_load(open(pfile))["USER"]
    import mario  # noqa: PLC0415

    print("loading base table…", flush=True)
    db = mario.parse_from_txt(paths["raw"], table="SUT", mode="flows")
    db.aggregate(str(ROOT / "support" / "aggregate_ee.xlsx"), ignore_nan=True)
    apply(db)
    EXPORT_DIR.mkdir(exist_ok=True)
    db.to_txt(path=str(EXPORT_DIR), scenario="baseline")
    print(f"export -> {EXPORT_DIR}", flush=True)


if __name__ == "__main__":
    main()
