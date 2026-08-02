# Nowcast — step 0 and the toy LP

- `step0_electricity_source_selector.py` — UNSD-first / EMBER-as-arbiter
  generation source selection per country (mix TVD) → `data/step0_selection.csv`
- `step0_implied_efficiency.py` — implied plant efficiencies from the UNSD
  balance (by plant type and by fuel; arbiter of the REVIEW pool) →
  `data/step0_efficiency.csv` (read by `support.nxbase_client.get_supply_mix_snapshot`)
- `toy_model/` — the cvxlab toy that validated the nowcast LP mechanics
  (masks in separate tables, relative L1 weights, elastic observations)
