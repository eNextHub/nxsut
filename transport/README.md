# Transport service layer — scripts & data

The nxsut transport disaggregation (design: `docs/transport_service_layer_plan.md`,
kept out of the public repo). Every input needed to reproduce the split lives in
`data/` (committed); heavy regenerable artifacts land in `out/` (gitignored).

## Script order (recipes / NXTR.V0)

1. `derive_recipes_v0.py` — recipe coefficients derived from nxbase-governed
   data (UNSD ÷ ITF, Eurostat road_go) → `data/derived_recipes_v0.csv`
2. `extract_fulfill_car.py` — EU car block from FULFILL_MARIO REF shocks
   → `data/fulfill_car_block.csv`
3. `build_nxtr_master.py` — assembles the NXTR.V0 inventory master
   (per-cell provenance) → `data/nxtr_master.xlsx` (ingested by nxbase as
   source `NXTR.V0`)

## Script order (Move B — splitting the transport sectors)

4. `moveb_implicit_prices.py` — SBS turnover ÷ observed volumes: banded
   implicit unit revenues → `data/moveb_implicit_prices.csv`
5. `build_moveb_split_master.py` — non-SBS monetary split key (tiers with
   per-cell provenance) → `data/moveb_split_master.csv`
6. `build_moveb_split_spec.py` — the full split spec, 49 EXIOBASE regions ×
   row classes → `data/moveb_split_spec.csv`
7. `apply_moveb_split.py` — dry-run on the real table (db never mutated;
   reversibility to float eps) → `data/moveb_split_dryrun.csv`
8. `apply_moveb_split_write.py` — writes the split (add_sectors register-only
   + deterministic surgery) → `out/_moveb_split_table/` (897 MB, regenerable)

Scripts 1-6 run in the repo venv against a local nxbase API; 7-8 run in the
MARIO conda env (see each docstring).
