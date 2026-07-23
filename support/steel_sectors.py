"""Add explicit steel & H2 production routes to an nxsut MARIO database.

Thin wrapper around MARIO's ``add_sectors`` machinery, driven by the
self-contained master workbook ported from ExioSteel / IAM COMPACT Study 9
(``support/add_sectors/Master_steel_h2.xlsx``). See
``support/add_sectors/README.md`` for provenance, the file inventory and the
compatibility caveat (the master's cluster sheets must match the labels of the
post-``aggregate_ee`` table).

This module only calls existing MARIO methods on the passed ``db`` — it makes
no changes to the MARIO package.
"""

from __future__ import annotations

import os

# Master lives next to this module, under add_sectors/.
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER = os.path.join(_HERE, "add_sectors", "Master_steel_h2.xlsx")


def add_steel_h2_sectors(db, master_path: str | None = None, *, read_inventories: bool = True):
    """Insert the steel + H2 routes into ``db`` in place and return it.

    Call **after** ``db.aggregate(...)`` and **before** the electricity
    supply-mix / trade updates in ``gen_v3.ipynb``.

    Parameters
    ----------
    db : mario.Database
        A parsed (and typically aggregated) hybrid SUT database.
    master_path : str, optional
        Path to the add_sectors master workbook. Defaults to the bundled
        ``support/add_sectors/Master_steel_h2.xlsx``.
    read_inventories : bool, default True
        Read the inventory sheets embedded in the master (the ExioSteel
        convention: the master is self-contained).
    """
    master_path = master_path or DEFAULT_MASTER
    if not os.path.exists(master_path):
        raise FileNotFoundError(
            f"add_sectors master not found: {master_path}\n"
            "Expected support/add_sectors/Master_steel_h2.xlsx "
            "(see support/add_sectors/README.md)."
        )

    n_before = len(db.get_index("Commodity"))
    db.read_add_sectors_excel(master_path, read_inventories=read_inventories)
    db.add_sectors()
    n_after = len(db.get_index("Commodity"))
    print(f"[steel_sectors] commodities: {n_before} -> {n_after} (+{n_after - n_before})")
    return db
