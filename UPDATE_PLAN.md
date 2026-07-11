# eNextSUT — All-Commodity Trade & Supply-Mix Update Plan

Working instructions for extending the eNextSUT database update beyond
electricity: refreshing the **trade mixes of (potentially) all commodities**
with BACI/Comtrade-class data and the **market shares of selected
commodities** with technology-mix statistics.

Status: planning. The electricity pipeline (v1.0/v2.0) is implemented in
`db_gen_new.ipynb` on the new MARIO methods and serves as the template for
everything below.

---

## 1. Where we start from

`db_gen_new.ipynb` builds the reference database from EXIOBASE Hybrid v3.3.18
in four moves, all native MARIO:

| Step | Method | What it does |
|---|---|---|
| Aggregate | `db.aggregate(...)` | electricity commodities → 1 `Electricity`; activities → EMBER technology labels |
| Supply mix | `db.update_supply_mix("electricity", year=..., ember_path=...)` | rewrites technology market shares on each region's `Electricity` column of `s` from EMBER data (plain-EMBER labels, raw full release and RoW regions handled natively; requires `db.meta.source` to mention EXIOBASE) |
| Pool | `db.pool_trade(["Electricity"])` | adds the `"{c} - supply"` / `"{c} - need"` pass-through layer; observed trade shares are written into `s` automatically |
| Trade mix | `db.update_trade_mix(shares, items=..., commodities=...)` | rewrites the origin shares of each destination market (one origins×destinations matrix per commodity as input) |

Key MARIO semantics to keep in mind (documented in the MARIO user guide,
pages *Update the electricity supply mix* and *Update trade mixes*):

- **Column totals are preserved**: every buyer keeps its total input of the
  item; only the split changes.
- **Subset rescaling**: labels/origins not listed in the shares keep their
  current share. Listing only foreign origins updates the sourcing among
  imports *without touching the domestic share* — this is the default
  strategy for Comtrade-class data, which cannot see domestic flows.
- **Chenery-Moses uniformity**: one destination-level mix applied to all
  buyer columns imposes uniform sourcing on those buyers. Fine (and more
  physical than Isard) for grid/bulk commodities; an information loss for
  differentiated goods.

## 2. Two regimes — do not pool everything

Pooling is a representation choice, not a prerequisite:

- **Pooled** (`pool_trade` + market shares in `s`): only for commodities whose
  trade we update repeatedly and where the market-share view is valuable —
  electricity now; candidates: natural gas, possibly transport fuels.
  Cost: each pooled commodity adds one activity + one commodity per region
  (~+49 rows/cols each on the full table). Pooling all ~200 commodities would
  nearly double the table — don't.
- **Isard-mode** (`update_trade_mix` directly on `u`/`Yc`, Commodity level):
  everything else. Same information applied, zero structural cost.

## 3. Work packages

### WP1 — Screening: which commodities get what

Data-driven shortlist before any data work:

1. From the baseline `s`, per commodity: number of activities with market
   share above a threshold (multi-producer structure) → supply-mix candidates.
2. Rank by footprint relevance (contribution to GHG/energy footprints) and
   trade volume (import share of total use, from `u`).
3. Output: one table `commodity → {trade: pooled | isard | skip, supply_mix:
   source | skip}` committed to this repo.

Expected supply-mix families (EXIOBASE already exposes the competing
activities): **primary vs `Re-processing of secondary X`** for steel,
aluminium, copper, other non-ferrous, paper, plastic, glass; electricity
(done); possibly heat/CHP and biofuel blending in transport fuels.

Preliminary tier list (from the post-aggregation activity/commodity labels;
to be confirmed by the screening):

- **Tier A — easy on both mixes**: Basic iron and steel (worldsteel EAF/BOF ×
  BACI HS72), Aluminium (IAI × HS76), Copper (ICSG × HS74), Pulp (FAO
  recovered-paper utilization × HS47/48), Lead-zinc-tin (ILZSG × HS78-80),
  Plastics basic (OECD Global Plastics Outlook, regional only × HS39).
- **Tier B — trade only** (single producer, footprint-heavy): crops (FAOSTAT
  detailed trade matrix, preferable to BACI for agriculture), coal qualities,
  crude, natural gas (IEA bilateral), refined products (HS2710 split, medium).
- **Tier C — mix with caveats**: glass (FEVE, EU only), cement/clinker (ash →
  clinker, GCCA/GNR clinker ratios, trade negligible), steam/hot water
  (multi-producer via CHP by-products, IEA, not traded — mix only, subset
  semantics ideal), fuel blending (Biogasoline/Biodiesels vs fossil fuels as a
  commodity-level use mix, IEA).
- **Tier D — skip**: differentiated manufacturing (weak CM assumption, no
  supply mix), services, waste treatment.

Suggested start: Tier A top-4 (steel, aluminium, copper, pulp) plus the
heaviest Tier B trade-only flows (fossil fuels, cereals).

### WP2 — Concordances

- **Product ↔ HS**: EXIOBASE ~200 products ↔ HS6, via the published
  EXIOBASE↔CPA/CPC↔HS crosswalks. Deliverable: one versioned CSV in
  `support/` (`concordance_hs_exiobase.csv`), many-to-one HS6 → product,
  with an explicit column for the aggregation weight basis (quantity/value).
- **Regions**: ISO3 ↔ EXIOBASE 44 regions + 5 RoW. Reuse MARIO's resolver
  (`mario.clusters.coverage`, EXIOBASE RoW members are packaged) — no new
  asset needed.

### WP3 — Trade adapter (goods)

- **Source: BACI (CEPII)** rather than raw Comtrade: mirror-reconciled,
  quantities in tonnes, one static yearly file (reproducibility over
  freshness). Raw Comtrade remains a fallback.
- Pipeline: BACI HS6 bilateral flows → concordance → per-commodity
  origins×destinations matrices (tonnes; value shares as fallback where
  quantities are unreliable) → **import-only shares** (origins summing to 1
  over foreign origins; the domestic share stays as observed in the table,
  by the subset-rescaling semantics).
- Output format: the same one `db_gen_new.ipynb` already consumes —
  `support/trades_{year}.xlsx`, one sheet per commodity, origins on rows,
  destinations on columns.
- **Energy carriers**: use IEA/Eurostat physical trade (energy units,
  consistent with the hybrid table) instead of HS tonnages. Electricity keeps
  the current EE-maps/ENTSO-E source.
- **Services**: no Comtrade coverage. v1: leave observed shares untouched.
  Later option: OECD-WTO BaTIS (EBOPS).
- **Known limitation** to document: gross bilateral flows include re-exports
  (Rotterdam/Hong Kong effect), while the table wants production-origin
  shares. BACI mitigates but does not eliminate this; accept and document in
  v1.

### WP4 — Supply-mix adapters

One adapter per family, shaped exactly like the EMBER one (label profile +
per-country-per-year shares source):

| Family | Competing activities | Source |
|---|---|---|
| Electricity | EMBER technologies | EMBER (done) |
| Steel | primary vs secondary re-processing | worldsteel (BOF/EAF by country) |
| Aluminium | primary vs secondary | IAI |
| Paper | virgin vs recycled | FAO / CEPI |
| Plastics | virgin vs recycled | PlasticsEurope / OECD |
| Heat | CHP / boilers | IEA balances |
| Transport fuels | fossil vs bio blending | IEA / EMBER |

Adapters live in `support/` first; stable ones can be promoted into MARIO as
packaged profiles (string modes like `"electricity"`) later.

### WP5 — Pipeline integration

- Extend `traded_commodities` and add a `supply_mix_sources` mapping in
  `db_gen_new.ipynb`; both loops already scale by construction
  (`meta.pooled_trade_map` carries the labels).
- **Performance gate**: the current `update_trade_mix` iterates
  destination×item with dense row rewrites. Fine for a handful of
  commodities; for ~150 commodities × 49 destinations on the full table it
  needs a vectorized bulk pass in MARIO (same API, faster engine). Benchmark
  first on ~10 commodities before requesting it.

### WP6 — Nowcasting levels (GDP / final demand benchmarks)

Mix and trade updates change the *composition* of the table and deliberately
preserve totals: the levels (Y, X, VA, emissions) stay at the base year of
EXIOBASE Hybrid 3.3.18 (2011). Nowcasting the levels is a separate, final
step:

1. **Scale final demand** per region × category, and per commodity family
   where physical benchmarks exist — a luxury of the hybrid units: IEA energy
   balances (TJ, same units as the table) for energy carriers, FAO food
   balances for food, apparent-consumption indices for materials; real
   GDP/consumption growth (WDI/AMECO) as the fallback scalar.
2. **Recompute** X, VA, E through the Leontief closure (MARIO: scaled `Y` via
   `update_scenarios` or a Percentage shock on `Y`).
3. **Benchmark ex post** — GDP from the monetary VA layer vs national
   accounts, energy totals vs IEA, CO2 vs EDGAR/GCB — and reconcile
   conflicting constraints with GRAS/RAS. Note: MARIO has a RAS balancing API
   on the unmerged `dev_gtap` branch; reconciling that branch is part of this
   work package.

Properties: composition and level updates commute (mixes preserve column
totals, Y scaling scales columns), so the order composition → levels →
reconciliation is a convention, not a constraint. Document explicitly that
technology recipes (`u`) and per-activity emission intensities stay at 2011
wherever no mix is updated — the same philosophy as EXIOBASE's own
extrapolated years and GLORIA nowcasts.

### WP7 — Validation & release

Automated checks at the end of the notebook (extend the existing footprint
comparison section):

1. Carbon intensity of electricity per region vs EMBER published values.
2. Import shares per (commodity, destination) vs BACI aggregates (round-trip).
3. Footprint comparison old-vs-new per release (existing section).
4. Balance check: `db.is_balanced("flows")` residual not worse than baseline.
5. Per-commodity changelog: what was updated, from which source, which
   regions fell back to other years.

Version the output as v3.0 (v1.0 = supply mixes only, v2.0 = + electricity
trades, v3.0 = + multi-commodity trades and mixes, v4.0 = + nowcast levels).

## 4. Conventions

- Pooled labels: `"{commodity} - supply"` / `"{commodity} - need"` (MARIO
  defaults; recorded in `db.meta.pooled_trade_map` — always read them from
  there, never hardcode).
- Trades input: `support/trades_{year}.xlsx`, one sheet per commodity,
  origins×destinations matrix, columns summing to 1 over the listed origins.
  Legacy shock-format workbooks are pivoted on the fly by the notebook.
- Set `db.meta.source` to a string containing "EXIOBASE" right after parsing:
  it enables the RoW region expansion in the EMBER (and future) adapters.
- Scenario names: `baseline` = updated mixes (v1.0 content), `ee_trades` =
  + updated trades. New scenarios per data vintage rather than overwriting.
- Requires MARIO ≥ the `dev` branch with `update_supply_mix`,
  `update_trade_mix`, `pool_trade` (see MARIO CHANGELOG, *Unreleased*).

## 5. Open decisions

- [ ] Pooling perimeter: electricity only, +gas, +fuels? (proposal: minimal,
      extend when a use case demands the market-share view)
- [ ] BACI vintage policy: pin one release per database version?
- [ ] Supply-mix shortlist: confirm the primary/secondary family after the
      WP1 screening, or start from steel+aluminium+paper directly?
- [ ] Domestic share: confirmed observed-only in v1 (import sourcing from
      BACI); revisit with production data (PRODCOM/IEA) in v2?
- [ ] GWP set for the validation footprints: AR4 (25/298, current v2.0
      convention) vs AR6 (29.8/273, used for the raw-table runs) — align.
- [ ] Nowcast target year and benchmark set (GDP only vs GDP + IEA energy +
      FAO food); whether reconciliation (RAS) is in scope for the first
      nowcast release.
