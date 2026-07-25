# nxsut

Reference supply-use database for the environmental impact analysis of
energy-transition technologies and energy policies, built from
**EXIOBASE Hybrid v3.3.18** with [MARIO](https://github.com/it-is-me-mario/MARIO).

The pipeline updates the *composition* of the table — electricity supply
mixes from [EMBER](https://ember-energy.org/) statistics and bilateral
electricity trade mixes — while preserving column totals. Raw inputs are
progressively governed in **nxbase**, the eNextGen data backbone, and reach
this pipeline through nxbase's public read-only API (see *Data access* below).

## Contents

| Path | What it is |
| --- | --- |
| `gen_v3.ipynb` | v3.0 generator (**current**): MARIO-native pipeline, EMBER supply mix + open ENTSO-E trade mix via the nxbase query API. Fully open input chain — the publishable version. |
| `calc_footprints.ipynb` | Footprint calculations on the generated database. |
| `support/` | Adapters and input files (aggregation maps, EMBER remapping, the nxbase query client) — being retrofitted into nxbase sources per WP0. |
| `paths.yml` | Public template for the per-user paths to raw inputs (EXIOBASE flows, EMBER release) and export target. Copy to `paths_personal.yml` (git-ignored) and fill in your real paths. |

## Requirements

- Python with `mario` ≥ the `dev` branch (needs `update_supply_mix`,
  `update_trade_mix`, `pool_trade`), `pandas`, `pyyaml`,
  `country_converter`.
- EXIOBASE Hybrid v3.3.18 flow files and the EMBER yearly full release
  (paths configured in `paths.yml`; not distributed with this repo).

## Data access

The pipeline reads its input data — EMBER electricity supply mixes and ENTSO-E
bilateral trades — from **nxbase's public read-only query API**. You do **not**
need an nxbase checkout (the nxbase repository is private): the API serves the
open-access sources **anonymously**, with no login or key.

- The API base URL is `nxbase_api` in `paths.yml`
  (default `https://enextgen.it/nxbase-api`). Point it at
  `http://127.0.0.1:8000` only if you run a local nxbase yourself.
- `support/nxbase_client.py` wraps the calls (`/data.csv`, `/sets/*`) and
  reshapes the rows into the structures MARIO consumes.
- Only open-visibility sources are anonymously reachable (EMBER generation,
  ENTSO-E trades, and the published nxsut releases).

## Versioning

- **v1.0 / v2.0** — legacy supply-mix / + bilateral electricity trades on the
  proprietary Electricity Maps mix. **Internal use only, not in this public
  repository** (`gen_v1.ipynb` / `gen_v2.ipynb` are git-ignored — the mix is not
  redistributable).
- **v2.1** — *retired* (2026-07-21): the MARIO-native pipeline on the
  proprietary Electricity Maps mix. Superseded by v3.0, same pipeline on an
  open mix.
- **v3.0 (current)** — MARIO-native pipeline, open ENTSO-E trade mix
  (`gen_v3.ipynb`). Fully open input chain — the publishable version.

## License

Licensed under **Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0)** — see [`LICENSE`](LICENSE). Share and adapt for any purpose,
including commercially, with appropriate credit and under the same license
(ShareAlike). nxsut derives from EXIOBASE Hybrid v3.3.18 (CC BY-SA 4.0), so the
ShareAlike term is inherited.

Copyright © 2026 Nicolò Golinucci, Lorenzo Rinaldi (eNextGen). Attribute as:
*"nxsut — Nicolò Golinucci & Lorenzo Rinaldi, eNextGen (CC BY-SA 4.0)"*.
