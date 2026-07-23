# Steel & H2 sector addition (from ExioSteel)

Support files to add **explicit steel and hydrogen production routes** to the
nxsut table via MARIO's `add_sectors` machinery. Ported from the ExioSteel /
IAM COMPACT Study 9 work so nxsut 3.x can carry disaggregated steel & H2
technologies (a *third lever* alongside the supply-mix and trade updates that
build v3.0).

## What add_sectors does

`add_sectors` is structural disaggregation: it inserts new activities and
commodities (here, steelmaking and H2 routes) into the table, wiring their
input recipes, outputs, final consumption and satellite (emission) accounts
from an inventory. It is driven by a single self-contained Excel **master**
(inventories read from its sheets), following the pattern in
[`scripts/add_sectors_exiosteel_reference.py`](scripts/add_sectors_exiosteel_reference.py):

```python
db.read_add_sectors_excel(master_path, read_inventories=True)
db.add_sectors()
```

## Files

| Path | What | Tracked in git |
| --- | --- | --- |
| `Master_steel_h2.xlsx` | The add_sectors master: steel + H2 routes (SR, DRI-EAF ×NG/COAL/H2/BECCS, BF-BOF-CCS/BECCS, H2 SR/COAL/ELZ ±CCS, AEL-EAF, MOE…), with `Commodities Clusters` / `Regions Clusters` mapping and inventory sheets. From IAM COMPACT Study 9. | ✅ |
| `inventories/steelmakingroutes.xlsx`, `inventories/blastfurnacegas.xlsx` | Source inventory workbooks the master is built from (process routes, blast-furnace / oxygen gas). | ✅ |
| `extensions/add_energy_accounts.xlsx` | Extra energy satellite accounts for the new sectors. | ✅ |
| `aggregations/*.xlsx` | Region/commodity aggregation helpers, incl. `aggr_to_EU27`, `aggr_to_EU12-EU15`, `aggr_to_EU` (relevant to the later EU disaggregation work) and `aggr_exio_382`. | ✅ |
| `scripts/add_sectors_exiosteel_reference.py` | The original ExioSteel driver, kept verbatim as reference (paths point to OneDrive ETE). | ✅ |
| `scripts/gcam_data_prep.py` | GCAM data prep for the steel mixes/imports (used to build the `data/` payloads). | ✅ |
| `data/Steel_mixes*.xlsx`, `data/Steel_imports.xlsx`, `data/Steel_consumption.xlsx`, `data/Electricity_mixes.xlsx` | GCAM-derived mix/trade payloads for the **later** steel supply-mix / trade updates (WP4/WP3), not needed for the add_sectors step itself. | ✅ (GCAM is open source / redistributable). Will move to nxbase governance per WP0 when the steel adapters land. |

## Where it slots into `gen_v3.ipynb`

Between the base parse+aggregate and the electricity mix/trade updates:

```text
parse_from_txt(raw, SUT, flows)
db.aggregate("support/aggregate_ee.xlsx")
► add steel + H2 sectors  ◄  (this folder)
db.update_supply_mix("electricity", …)   # EMBER
db.pool_trade(["Electricity"])
db.update_trade_mix(…)                    # ENTSO-E
db.to_txt(…)
```

Ready-to-use call (see `support/steel_sectors.py`):

```python
from support import steel_sectors
db = steel_sectors.add_steel_h2_sectors(db)   # reads Master_steel_h2.xlsx
```

## ⚠️ Compatibility check before first run

The master was authored against **EXIOBASE Hybrid Energy Transition Edition**
(ExioSteel), whereas nxsut parses **EXIOBASE Hybrid 3.3.18 (with VA)** and then
applies `support/aggregate_ee.xlsx`. `add_sectors` maps the new sectors onto
existing commodities/regions through the master's `Commodities Clusters` /
`Regions Clusters` sheets — **those labels must match the post-`aggregate_ee`
table**. Before wiring this into the pipeline, verify:

1. the commodity labels referenced in the master exist in the aggregated table;
2. the region set matches (44 + 5 RoW vs the aggregated region set);
3. the units of the new commodities are consistent with the hybrid table (the
   `DB units` sheet).

Mismatches are label-mapping fixes in the master's cluster sheets, not code
changes. **No MARIO package edits** are to be made without explicit sign-off.
