# Steel & H2 sector addition

Adds **explicit steel and hydrogen production routes** to the nxsut table via
MARIO's `add_sectors`. The inventory (22 routes from Ghezzi et al. 2026 / IAM
COMPACT Study 9) is **governed in nxbase** as an add_sectors unit-process
recipe (source `Ghezzi et al. 2026 - steel & H2 inventory`); this folder keeps
only the **base-DB attachment** the pipeline needs on top of that recipe.

## The files here

| Path | What |
| --- | --- |
| `Master_steel_h2.xlsx` | The add_sectors **master template**: `Master` placement sheet (region / market share / parent activity / DB Item clusters), `Commodities Clusters` / `Regions Clusters`, `DB units`, and the 22 per-route inventory sheets. |
| `blastfurnacegas.xlsx` | The **furnace-gas reallocation** master: two empty gas-production activities (Blast / Oxygen Steel Furnace Gas) fed to a second `add_sectors` after the routes, used by the reallocation cell below. |

At run time `gen_v3.ipynb` does **not** use this file's quantities directly.
`support/nxbase_client.build_add_sectors_master(...)` reads the recipe
(quantities + backbone-anchored items) from the nxbase API and rewrites the
master's `Quantity` column from it, keeping the template's clusters / placement
/ DB-Item mapping. The result is a transient `_steel_master.xlsx` (gitignored).

## Where it slots into `gen_v3.ipynb`

`add_sectors` runs **after** `aggregate_ee`: the routes attach to the single
aggregated grid `Electricity`, and the pre-existing EMBER electricity
activities keep their supply coefficients. (Running `add_sectors` *before*
`aggregate` drops those activities from the `s` block, which breaks
`update_supply_mix`; running it after — with the ETE electricity DB Items /
cluster fixed, see below — keeps `s` intact.)

```python
db.aggregate('support/aggregate_ee.xlsx', ignore_nan=True)
nxc.build_add_sectors_master('support/add_sectors/Master_steel_h2.xlsx',
                             '_steel_master.xlsx', api_url=nxbase_api)
db.read_add_sectors_excel('_steel_master.xlsx', read_inventories=True)
db.add_sectors()
```

## Furnace-gas emission reallocation (ExioSteel method)

Right after the routes, a **second** `add_sectors` (from `blastfurnacegas.xlsx`)
introduces two fictitious activities that produce the blast / oxygen furnace
gases. The steel sector's supply of those gases is zeroed and its `U`/`V`/`E` are
recomputed on its steel supply alone (`/ S_main`, not `/ X`): the footprint is
then per tonne of *actual steel*, not diluted across the co-product gases, and
the gases become emission-free carriers (their embodied steel emissions no longer
leak into whoever burns them — e.g. electricity). See the cell right after
`add_sectors` in `gen_v3.ipynb`.

## Base-DB attachment (pipeline-side, not in nxbase)

nxbase holds the *generic* recipe (backbone-anchored concepts). The mapping of
each concept to **this** base table's labels stays here, in
`build_add_sectors_master`:

- **clusters / DB Item** — e.g. `Carbon dioxide, fossil → CO2`, `Coke Oven Coke
  → Coke`; and the post-aggregate electricity remap `Electricity / Electricity
  RES → Electricity` (the single grid commodity `aggregate_ee` produces).
- **ETE electricity cluster** — the template's `Commodities Clusters` sheet
  groups generation-split electricity commodities (`Coal`, `Hydro`, `Solar`…)
  that exist only in the ExioSteel ETE base, not here — and `Coal` collides
  with the aggregated EMBER **activity** label. `build_add_sectors_master`
  clears that sheet for our base.
- **placement** — GLOBAL region, market share, parent activity — read from the
  template's `Master` sheet.

A finer electricity attachment is a known later refinement. **No MARIO package
edits** without explicit sign-off.
