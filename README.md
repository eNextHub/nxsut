# nxsut

Reference supply-use database for the environmental impact analysis of
energy-transition technologies and energy policies, built from
**EXIOBASE Hybrid v3.3.18** with [MARIO](https://github.com/it-is-me-mario/MARIO).

The pipeline updates the *composition* of the table — electricity supply
mixes from [EMBER](https://ember-energy.org/) statistics and bilateral
electricity trade mixes — while preserving column totals. Raw inputs are
progressively governed in [nxbase](https://github.com/eNextHub/nxbase),
the eNextGen data backbone, and reach this pipeline as materialized
exports.

## Contents

| Path | What it is |
| --- | --- |
| `UPDATE_PLAN.md` | The working plan: goal, work packages (WP0–WP8), conventions, open decisions. **Start here.** |
| `db_gen.ipynb` | Database generator: parse → aggregate → supply mix → pooled trade → trade mix. |
| `calc_footprints.ipynb` | Footprint calculations on the generated database. |
| `support/` | Adapters and input files (trade workbooks, aggregation maps, EMBER remapping) — being retrofitted into nxbase sources per WP0. |
| `paths.yml` | Per-user paths to raw inputs (EXIOBASE flows, EMBER release) and export target. Add your own user key. |
| `_old/` | Superseded notebooks, kept for reference. |

## Requirements

- Python with `mario` ≥ the `dev` branch (needs `update_supply_mix`,
  `update_trade_mix`, `pool_trade`), `pandas`, `pyyaml`,
  `country_converter`.
- EXIOBASE Hybrid v3.3.18 flow files and the EMBER yearly full release
  (paths configured in `paths.yml`; not distributed with this repo).

## Versioning

- **v1.0** — updated electricity supply mixes.
- **v2.0/v2.1** — + updated bilateral electricity trades.
- **v3.0 (target)** — P1 energy-carrier trades + mixes, first benchmark
  report, raw inputs governed in nxbase. See `UPDATE_PLAN.md` §WP8.
