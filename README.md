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
| `gen_v1.ipynb` | v1.0 generator: legacy supply-mix update only, no trade layer. |
| `gen_v2.ipynb` | v2.0 generator: legacy supply mix + legacy pooled trade on the proprietary Electricity Maps mix. Standalone (re-derives everything `gen_v1.ipynb` does). |
| `gen_v3.ipynb` | v3.0 generator (**current**): MARIO-native pipeline, EMBER supply mix + open ENTSO-E trade mix via the nxbase query API. Fully open input chain — the publishable version. Includes a v2.0-vs-v3.0 footprint comparison. |
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

- **v1.0** — updated electricity supply mixes (`gen_v1.ipynb`).
- **v2.0** — + updated bilateral electricity trades, proprietary Electricity
  Maps mix (`gen_v2.ipynb`). Internal use only — the mix is not
  redistributable.
- **v2.1** — *retired* (2026-07-21): the MARIO-native pipeline on the
  proprietary Electricity Maps mix. Superseded by v3.0, same pipeline on an
  open mix.
- **v3.0 (current)** — MARIO-native pipeline, open ENTSO-E trade mix
  (`gen_v3.ipynb`). Fully open input chain — the publishable version. See
  `UPDATE_PLAN.md` §WP8.
