"""Move B (c), stage 2a — dry-run of the deterministic split on the real table.

Loads the EXIOBASE Hybrid 3.3.18 base (the gen_v3 working grid:
``parse_from_txt`` + ``aggregate_ee``), extracts the two parent blocks per
region ("Other land transportation services" -> road_pipe children,
"Railway transportation services" -> rail children) and applies the split
spec (``moveb_split_spec.csv``) **in extracted-matrix space** — the db is
never mutated. Stage 2b will write the children back via ``add_sectors``.

What is validated here, per region:

- column split (U + V + E): liquid-fuel rows by the bottom-up shares, all
  other rows by the 'other' shares; **E follows the fuel shares**
  (transport emissions are combustion-driven — declared v0);
- use-row split (U row + Y row): initial allocation by the
  final/intermediate rule (final users -> PAX; activity users -> FRT+PIPE
  by their supply ratio; business-travel exception deferred to 2b),
  closed by the **per-row IPF** (row targets = supply split x M, columns
  = parent cells preserved);
- **reversibility**: re-aggregated children == parent, exact to float eps,
  on every block (the acceptance test);
- diagnostics: child sizes, implied prices vs the observed Q (cross-check
  against diagnostic (a)), fuel content of the HGV child.

Run in the MARIO conda env:

    unset VIRTUAL_ENV; caffeinate -is /opt/anaconda3/envs/mario/bin/python \
        transport/apply_moveb_split.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent

# (activity name, commodity name) in the hybrid grid. Discovery 2026-08-02:
# "Transport via pipelines" is ALREADY a separate sector in EXIOBASE hybrid
# (the NACE 1.1 division-60 split: 601 rail / 602 road / 603 pipelines) —
# the PIPE child is not needed; the road block's SBS shares renormalise
# without it at load (consistent with the (a) verdict: pipe stays MEUR).
PARENTS = {
    "road_pipe": ("Other land transport", "Other land transportation services"),
    "rail": ("Transport via railways", "Railway transportation services"),
    "sea": ("Sea and coastal water transport",
            "Sea and coastal water transportation services"),
    "iww": ("Inland water transport", "Inland water transportation services"),
    "air": ("Air transport (62)", "Air transport services (62)"),
}
CHILDREN = {"road_pipe": ["ROAD.FRT", "ROAD.PAX"], "rail": ["TRN.P", "TRN.F"],
    "sea": ["SEA.FRT", "SEA.PAX"], "iww": ["IWW.FRT", "IWW.PAX"],
    "air": ["AIR.FRT", "AIR.PAX"],
}
# children with no open pkm anywhere (only "passengers carried"): they keep
# the monetary denomination, as PIPE does — declared, never synthesised.
# every transport child is now physical: air passenger-km derive
# from ICAO, sea passenger-km come from Eurostat, and inland
# waterway passengers — which no statistical system collects, by
# the explicit exclusion in Regulation (EC) 1365/2006 — are scaled
# with the sea passenger price (declared proxy, tiny sector).
MONETARY_CHILDREN: set[str] = set()
PRICE_PROXY = {"IWW.PAX": "SEA.PAX"}
# liquid-fuel commodity names in the hybrid grid (matched against the index;
# what is actually found is printed — no silent assumptions).
FUEL_NAMES = [
    "Motor Gasoline", "Gas/Diesel Oil", "Liquefied Petroleum Gases (LPG)",
    "Biogasoline", "Biodiesels", "Other Liquid Biofuels", "Kerosene",
    "Heavy Fuel Oil", "Natural Gas Liquids",
]
FINAL_PAX = ["Final consumption expenditure by households",
             "Final consumption expenditure by non-profit organisations",
             "Final consumption expenditure by government"]


def load_spec() -> dict:
    """Load the spec; PIPE is dropped and the road shares renormalised
    (pipelines are already their own sector in the grid)."""
    spec: dict = defaultdict(dict)
    with open(HERE / "data" / "moveb_split_spec.csv") as f:
        for r in csv.DictReader(f):
            if r["child"] == "PIPE":
                continue
            spec[(r["region"], r["block"], r["row_class"])][r["child"]] = float(r["share"])
    for (region, block, row_class), shares in spec.items():
        if row_class in ("other", "fuel_liquid"):
            tot = sum(shares.values())
            if tot > 0:
                for c in shares:
                    shares[c] /= tot
    return spec


def ipf(alloc: pd.DataFrame, row_targets: pd.Series, col_targets: pd.Series,
        iters: int = 30) -> pd.DataFrame:
    """Tiny per-row IPF: children x users, ends on the column step so the
    parent cells are preserved exactly."""
    a = np.array(alloc.to_numpy(), dtype=float)   # explicit copy: pandas-3 CoW
    rt = np.array(row_targets.to_numpy(), dtype=float)
    ct = np.array(col_targets.to_numpy(), dtype=float)
    for _ in range(iters):
        rs = a.sum(axis=1)
        nz = rs > 0
        a[nz] *= (rt[nz] / rs[nz])[:, None]
        cs = a.sum(axis=0)
        nz = cs > 0
        a[:, nz] *= ct[nz] / cs[nz]
    return pd.DataFrame(a, index=alloc.index, columns=alloc.columns)


def main() -> None:
    pfile = ROOT / ("paths_personal.yml" if (ROOT / "paths_personal.yml").exists()
                    else "paths.yml")
    paths = yaml.safe_load(open(pfile))["USER"]

    import mario  # noqa: PLC0415 (mario env only)

    print("loading base table…", flush=True)
    db = mario.parse_from_txt(paths["raw"], table="SUT", mode="flows")
    db.aggregate(str(ROOT / "support" / "aggregate_ee.xlsx"), ignore_nan=True)
    regions = list(db.get_index("Region"))
    print(f"grid: {len(regions)} regioni, "
          f"{len(db.get_index('Activity'))} activity, "
          f"{len(db.get_index('Commodity'))} commodity", flush=True)

    acts = list(db.get_index("Activity"))
    coms = list(db.get_index("Commodity"))
    for block, (act_name, com_name) in PARENTS.items():
        assert act_name in acts, f"parent activity '{act_name}' non trovata"
        assert com_name in coms, f"parent commodity '{com_name}' non trovata"
    fuels = [c for c in FUEL_NAMES if c in coms]
    print(f"fuel rows trovate ({len(fuels)}): {fuels}", flush=True)

    spec = load_spec()
    U, V, E, S, Y = db.U, db.V, db.E, db.S, db.Y

    max_col_err = max_row_err = 0.0
    diag_rows: list[dict] = []
    for region in regions:
        for block, (act_name, com_name) in PARENTS.items():
            children = CHILDREN[block]
            sh_other = spec[(region, block, "other")]
            sh_fuel = spec[(region, block, "fuel_liquid")]

            # --- column split: U + V + E ---
            u_col = U[(region, "Activity", act_name)]
            fuel_mask = u_col.index.get_level_values(2).isin(fuels)
            child_cols = {}
            for c in children:
                col = u_col * sh_other.get(c, 0.0)
                col[fuel_mask] = u_col[fuel_mask] * sh_fuel.get(c, 0.0)
                child_cols[c] = col
            recon = sum(child_cols.values())
            err = float((recon - u_col).abs().max())
            max_col_err = max(max_col_err, err)

            v_col = V[(region, "Activity", act_name)]
            e_col = E[(region, "Activity", act_name)]
            child_v = {c: v_col * sh_other.get(c, 0.0) for c in children}
            child_e = {c: e_col * sh_fuel.get(c, 0.0) for c in children}
            err_e = float((sum(child_e.values()) - e_col).abs().max())
            max_col_err = max(max_col_err, err_e,
                              float((sum(child_v.values()) - v_col).abs().max()))

            # --- use row (U + Y) with rule + IPF ---
            u_row = U.loc[(region, "Commodity", com_name), :]
            y_row = Y.loc[(region, "Commodity", com_name), :]
            users = pd.concat([u_row, y_row])
            M = float(users.sum())
            if M <= 0:
                continue
            is_final_pax = np.array(
                [(lvl[1] != "Activity" and any(k in str(lvl[2]) for k in
                  ("households", "non-profit", "government")))
                 for lvl in users.index], dtype=bool)
            pax = next(c for c in children if c.endswith("PAX") or c == "TRN.P")
            frt = next(c for c in children if c.endswith("FRT") or c == "TRN.F")
            # negative cells (inventory changes etc.): split by the supply
            # shares OUTSIDE the IPF — deterministic, sign-preserving, and
            # the remaining row targets stay consistent by construction.
            neg = users.clip(upper=0.0)
            pos = users.clip(lower=0.0)
            # seed: 90% rule + 10% proportional (the declared business-travel
            # allowance — also gives the IPF no unreachable zero structure).
            delta = 0.10
            rule = pd.DataFrame(0.0, index=children, columns=users.index)
            rule.loc[pax, is_final_pax] = pos[is_final_pax]
            rule.loc[frt, ~is_final_pax] = pos[~is_final_pax]
            prop = pd.DataFrame(
                np.outer([sh_other.get(c, 0.0) for c in children], pos.to_numpy()),
                index=children, columns=users.index)
            seed = (1 - delta) * rule + delta * prop
            row_targets = pd.Series(
                {c: sh_other.get(c, 0.0) * float(pos.sum()) for c in children})
            closed_pos = ipf(seed, row_targets, pos)
            neg_split = pd.DataFrame(
                np.outer([sh_other.get(c, 0.0) for c in children], neg.to_numpy()),
                index=children, columns=users.index)
            closed = closed_pos + neg_split
            err_c = float((closed.sum(axis=0) - users).abs().max())
            err_r = float((closed_pos.sum(axis=1) - row_targets).abs().max()
                          / max(float(pos.sum()), 1))
            max_col_err = max(max_col_err, err_c)
            max_row_err = max(max_row_err, err_r)

            # --- diagnostics ---
            q_spec = spec.get((region, block, "Q"), {})
            for c in children:
                m_child = sh_other.get(c, 0.0) * M
                q = q_spec.get(c, 0.0)
                diag_rows.append(dict(
                    region=region, block=block, child=c,
                    MEUR=round(m_child, 1),
                    Q=round(q, 1) if q else "",
                    implied_price=round(m_child / q, 4) if q else "",
                ))

    out = HERE / "data" / "moveb_split_dryrun.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "block", "child", "MEUR",
                                          "Q", "implied_price"])
        w.writeheader()
        w.writerows(diag_rows)

    print(f"\nREVERSIBILITA': max errore colonne/celle = {max_col_err:.3e}  "
          f"max errore riga (rel, IPF) = {max_row_err:.3e}", flush=True)
    print(f"{len(diag_rows)} righe diagnostica -> {out}")
    for region in ("IT", "DE", "US", "CN"):
        sel = [r for r in diag_rows if r["region"] == region]
        line = "  ".join(f"{r['block'][0]}/{r['child']}={r['MEUR']}"
                         + (f"@{r['implied_price']}" if r["implied_price"] else "")
                         for r in sel)
        print(f"  {region}: {line}")


if __name__ == "__main__":
    main()
