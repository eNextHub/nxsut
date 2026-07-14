# nxsut — Energy-Chain Reference & Benchmark Plan

Working instructions for developing nxsut into a **reference database for
the environmental impact analysis of energy-transition technologies and
energy policies**. The update machinery
(trade mixes from bilateral trade statistics, market shares from
technology-mix statistics) is unchanged, but perimeter and priorities are
set by that goal: fidelity of the energy supply chain first, a benchmark
pipeline against independent data as a first-class deliverable, level
nowcasting deferred. nxsut develops hand in hand with **nxbase**, the
eNextGen data backbone where every raw input becomes a governed, versioned
source (WP0).

Status: **WP0 closed (2026-07-14)**. The electricity pipeline
(v1.0/v2.0/v2.1) is implemented in `db_gen.ipynb` (superseded notebooks live
in `_old/`) on the new MARIO methods and serves as the template for
everything below. Both of its raw inputs — EMBER generation and the
Electricity Maps bilateral trades — are governed in nxbase and consumed
through the **nxbase query API** via `support/nxbase_client.py`, with
round-trip acceptance tests in `tests/`. Next up: WP1 screening.

---

## 0. Goal and priorities

The database has one precise job: supporting reliable statements about the
environmental impacts of energy technologies and energy policies. Four
consequences:

1. **Energy-chain fidelity first.** The supply chains that feed energy
   technologies — carriers, conversion steps, and the materials that
   dominate embodied impacts — get updated mixes and trades before anything
   else. Generic all-commodity coverage is no longer a target in itself.
2. **Benchmarking is a standing pipeline, not a release gate.** Every
   version ships with a reproducible comparison of table-derived indicators
   against independent references (IEA, EMBER, EDGAR/GCB, LCA literature).
   The credibility of the energy representation *is* the product.
3. **Raw data are governed in nxbase, not scattered.** Every dataset
   feeding the pipeline — mix statistics, bilateral trades, benchmark
   references — is ingested into nxbase as a `source` with a reusable
   `parser` recipe, and reaches the pipeline through materialized exports.
   No new loose files in `support/` (WP0).
4. **Nowcasting the levels is deferred.** It stays on the roadmap (WP7) and
   will reuse the benchmark suite as its constraint set, but it comes after
   the energy chain is right — and measurably so.

Priority ladder:

- **P1 — energy carriers & conversion**: electricity (done), natural gas,
  coal, crude oil, refined products, biofuels/blending, heat & CHP.
- **P2 — energy-technology supply chains**: the materials that dominate the
  embodied impacts of transition technologies — steel, aluminium, copper,
  cement/clinker, glass, plastics (and their primary/secondary splits).
- **P3 — everything else**: only where cheap and demonstrably relevant to
  the footprints of P1/P2 chains; otherwise skip.

## 1. Where we start from

`db_gen.ipynb` builds the reference database from EXIOBASE Hybrid v3.3.18
in four moves, all native MARIO:

| Step | Method | What it does |
| --- | --- | --- |
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
  strategy for trade data that cannot see domestic flows.
- **Chenery-Moses uniformity**: one destination-level mix applied to all
  buyer columns imposes uniform sourcing on those buyers. Fine (and more
  physical than Isard) for grid/bulk commodities — which is exactly the P1
  perimeter; an information loss for differentiated goods.

## 2. Two regimes — do not pool everything

Pooling is a representation choice, not a prerequisite:

- **Pooled** (`pool_trade` + market shares in `s`): only for commodities whose
  trade we update repeatedly and where the market-share view is valuable —
  electricity now; candidates: natural gas, possibly transport fuels.
  Cost: each pooled commodity adds one activity + one commodity per region
  (~+49 rows/cols each on the full table). Pooling everything would nearly
  double the table — don't.
- **Isard-mode** (`update_trade_mix` directly on `u`/`Yc`, Commodity level):
  everything else. Same information applied, zero structural cost.

## 3. Work packages

### WP0 — nxbase data backbone (parallel track)

nxbase (repo: [github.com/eNextHub/nxbase](https://github.com/eNextHub/nxbase),
local sibling checkout; knowledge base in `docs/knowledge/`, in Italian —
nxsut stays English) is the relational home of eNextGen's ESG/energy data:
a `data` table fed source-first by reusable `parser` recipes, with a
Rosetta-Stone parent-child set hierarchy for cross-nomenclature
reconciliation. nxsut is its first structured customer: the datasets used
to build nxsut from EXIOBASE Hybrid 3.3.18 drive the parser roadmap.

Division of labour (same pattern as the GHG/GWP case, already live):
**nxbase** governs raw data and mappings and materializes exports;
**MARIO/nxsut** does the table algebra and gives footprints back for
ingestion (`from_mario`).

Current inputs to retrofit (they define the first parser recipes):

| Raw input | Today | Target in nxbase |
| --- | --- | --- |
| Electricity bilateral trades, hand-scraped from Electricity Maps | **done** — one source `EMAPS` with `period_range` (period slices, not versions), glob path over the committed legacy workbooks; consumed via `get_trade_matrix()` | ~~one `source` per vintage + parser~~ |
| EMBER yearly full release (supply mixes) | **done** — source `EMBER25` + `from_csv` parser (45,429 OUT rows); consumed via `get_ember_snapshot()` | ~~exporter feeds `update_supply_mix`~~ |
| GWP factors & GHG label mapping | were hardcoded in MARIO | **done** — governed in nxbase, exported via `export-mario-ghg`; the pattern to copy |
| EXIOBASE Hybrid 3.3.18 flows | OneDrive (`paths.yml: raw`) | stays a file input to MARIO (deliberately *not* an nxbase source — see the GHG bridge doc); MARIO-computed footprints are ingested back via `from_mario` |

Sources the plan will need, one parser per family, aligned with the WPs
that consume them: IEA WEB + bilateral energy trade (WP3a, WP4, WP6.2),
BACI (WP3b), worldsteel / IAI / ICSG / OECD plastics (WP4), EMBER published
intensities + EDGAR/GCB + LCA reference sets (WP6).

**API-first interface (decided 2026-07-13, supersedes the exporter
plan):** nxbase exposes its data only through the query API (`/data`,
`/data.csv`, `/sets/*` — live SQL on Postgres, local today, Supabase in
phase 2). The pipeline consumes it via `support/nxbase_client.py`, which
reshapes API rows into what MARIO already reads (reduced EMBER snapshot,
origins x destinations trade matrices) and logs the provenance (nxbase
version + source vintages) at every run. Deferred, optional: MARIO could
accept `ember_data=` as a DataFrame (provider-agnostic) so the transient
snapshot file disappears — not required.

Rule for what comes next: every **new** adapter (WP3/WP4/WP6) is born as
an nxbase parser + client function, never as another loose file in
`support/`.

### WP1 — Screening: size the energy perimeter

Data-driven confirmation of the priority ladder before any data work:

1. **Footprint decomposition of the energy chains**: from the baseline,
   decompose the GHG/energy footprint of each electricity technology and
   energy carrier into upstream commodity contributions → which flows
   actually matter for technology assessments. This — not generic footprint
   relevance — is what promotes a commodity into P2.
2. Per commodity in P1/P2: import share of total use (from `u`) and
   multi-producer structure in `s` (market shares above a threshold) →
   trade-update and supply-mix candidates respectively.
3. Output: one table `commodity → {priority: P1 | P2 | P3, trade: pooled |
   isard | skip, supply_mix: source | skip}` committed to this repo.

Expected perimeter (from the post-aggregation labels; to be confirmed):

- **P1 carriers**: natural gas (IEA bilateral trade; pooling candidate),
  coal qualities, crude oil, refined products (HS2710 split, medium),
  fuel blending (Biogasoline/Biodiesels vs fossil fuels as a
  commodity-level use mix, IEA), steam/hot water (multi-producer via CHP
  by-products, not traded — mix only, subset semantics ideal), electricity
  (done).
- **P2 materials**: Basic iron and steel (worldsteel EAF/BOF × BACI HS72),
  Aluminium (IAI × HS76), Copper (ICSG × HS74), cement/clinker (ash →
  clinker, GCCA/GNR clinker ratios, trade negligible), glass (FEVE, EU
  only), Plastics basic (OECD Global Plastics Outlook, regional only ×
  HS39).
- **P3 / skip**: crops & food, pulp & paper, differentiated manufacturing,
  services, waste treatment — revisit only if the WP1 decomposition shows a
  material contribution to P1/P2 footprints.

Suggested start: gas + coal + crude + refined products (trades), heat and
fuel blending (mixes), then steel + aluminium + copper.

### WP2 — Concordances

Long-term, cross-nomenclature mappings are exactly what nxbase's
Rosetta-Stone set hierarchy is for: concordances should live there as
parent-child relations between classifications, with the CSVs below as
seeds / materialized views, not as the primary home.

- **Energy carriers ↔ IEA products** (P1): energy flows bypass HS — the
  natural source is IEA (products × flows, energy units). Deliverable: a
  small hand-curated mapping IEA product codes ↔ EXIOBASE energy
  commodities (`support/concordance_iea_exiobase.csv`).
- **Product ↔ HS** (P2 materials): EXIOBASE products ↔ HS6 via the
  published EXIOBASE↔CPA/CPC↔HS crosswalks, restricted to the P2 shortlist
  (tens of HS headings, not the full ~5000). Deliverable:
  `support/concordance_hs_exiobase.csv`, many-to-one HS6 → product, with an
  explicit column for the aggregation weight basis (quantity/value).
- **Regions**: ISO3 ↔ EXIOBASE 44 regions + 5 RoW. Reuse MARIO's resolver
  (`mario.clusters.coverage`, EXIOBASE RoW members are packaged) — no new
  asset needed; nxbase's canonical `site` set is the eventual home.

### WP3 — Trade adapters

Each adapter = nxbase parser (raw → `data`) + exporter (→ the
origins×destinations workbook the notebook consumes), per WP0.

#### 3a — Energy carriers (P1, first)

- Source: IEA World Energy Balances + bilateral trade (imports by origin /
  exports by destination); Eurostat for intra-EU detail. Energy units,
  consistent with the hybrid table. Electricity keeps the current
  EE-maps/ENTSO-E source.
- Because balances report production alongside imports, the **full origin
  mix including the domestic share is observable** for carriers — unlike
  HS-based trade. Decide per carrier whether to update the domestic split
  too or stay import-only (subset rescaling).
- Output format: the same one `db_gen.ipynb` already consumes —
  `support/trades_{year}.xlsx`, one sheet per commodity, origins on rows,
  destinations on columns.

#### 3b — Materials (P2, second)

- Source: **BACI (CEPII)** rather than raw Comtrade: mirror-reconciled,
  quantities in tonnes, one static yearly file (reproducibility over
  freshness). Raw Comtrade remains a fallback.
- Pipeline: BACI HS6 bilateral flows → concordance → per-commodity
  origins×destinations matrices (tonnes; value shares as fallback where
  quantities are unreliable) → **import-only shares** (origins summing to 1
  over foreign origins; the domestic share stays as observed in the table,
  by the subset-rescaling semantics).
- **Known limitation** to document: gross bilateral flows include
  re-exports (Rotterdam/Hong Kong effect), while the table wants
  production-origin shares. BACI mitigates but does not eliminate this;
  accept and document.

**Services**: out of scope (P3). If ever needed: OECD-WTO BaTIS (EBOPS).

### WP4 — Supply-mix adapters

One adapter per family, shaped exactly like the EMBER one (label profile +
per-country-per-year shares source), in priority order — and, per WP0, each
backed by an nxbase source + parser rather than a loose file:

| Family | Competing activities | Source | Priority |
| --- | --- | --- | --- |
| Electricity | EMBER technologies | EMBER (done) | P1 |
| Heat | CHP / boilers | IEA balances | P1 |
| Transport fuels | fossil vs bio blending | IEA / EMBER | P1 |
| Steel | primary vs secondary re-processing | worldsteel (BOF/EAF by country) | P2 |
| Aluminium | primary vs secondary | IAI | P2 |
| Plastics | virgin vs recycled | PlasticsEurope / OECD | P2 |
| Paper | virgin vs recycled | FAO / CEPI | P3 |

Adapters live in `support/` first; stable ones can be promoted into MARIO as
packaged profiles (string modes like `"electricity"`) later.

### WP5 — Pipeline integration

- Extend `traded_commodities` and add a `supply_mix_sources` mapping in
  `db_gen.ipynb`; both loops already scale by construction
  (`meta.pooled_trade_map` carries the labels).
- **Performance note**: the current `update_trade_mix` iterates
  destination×item with dense row rewrites. The energy-first perimeter is
  tens of commodities, not ~150, so the vectorized bulk pass in MARIO may
  not be needed at all — benchmark on ~10 commodities before requesting it.

### WP6 — Benchmark pipeline (core deliverable)

A standing, versioned comparison of table-derived indicators against
independent references. Runs at the end of every `db_gen.ipynb` execution
(or as a dedicated `benchmark.ipynb`) and produces one tidy CSV of
`(indicator, region, table_value, reference_value, source, vintage)` plus a
short report per release. Reference values are themselves data: their
natural home is nxbase (one `source` per reference, with vintage), queried
or exported by the benchmark notebook; `support/benchmarks/` snapshot files
are the interim cache until the corresponding parsers exist.

Benchmark families, in order of implementation:

1. **Electricity mix & carbon intensity** per region vs EMBER published
   values (partly exists in the footprint-comparison section — formalize).
2. **Energy balances**: production, transformation and final use per
   carrier×region vs IEA WEB — direct unit match (TJ) thanks to the hybrid
   table.
3. **Technology footprints**: gCO2eq/kWh per electricity technology per
   region vs LCA literature ranges (UNECE 2021, IPCC AR5 Annex III,
   ecoinvent where licensed); gCO2eq/MJ for fuel supply chains vs
   well-to-tank literature (e.g. JEC WTW).
4. **Emission totals**: territorial CO2/GHG per region vs EDGAR / Global
   Carbon Budget / UNFCCC inventories.
5. **Trade round-trip & coverage**: import shares per (carrier,
   destination) vs the injected source (IEA/Eurostat/BACI) — closes the
   loop on the update itself — plus coverage stats for what was *not*
   updated.
6. **Policy indicators**: embodied carbon in electricity / gas / fuel
   imports per region — plausibility vs literature; these double as
   showcase outputs of the database.

GWP handling: the aggregation schemes (AR4/AR5/AR6 baskets) are governed in
nxbase and exported to MARIO via `export-mario-ghg` — the footprint and
benchmark calculations should consume that export, not MARIO's legacy
hardcoded dictionaries. Computed footprints flow back into nxbase
(`from_mario`), closing the loop.

Plus the structural checks: `db.is_balanced("flows")` residual not worse
than baseline; per-commodity changelog (what was updated, from which
source, which regions fell back to other years).

Acceptance policy: start with documented deviations (value, reference,
explanation) rather than hard thresholds; graduate to thresholds once the
pipeline is stable.

### WP7 — Nowcasting levels (deferred)

Mix and trade updates change the *composition* of the table and deliberately
preserve totals: the levels (Y, X, VA, emissions) stay at the base year of
EXIOBASE Hybrid 3.3.18 (2011). Nowcasting the levels is a separate, later
step — deliberately after WP6, because the benchmark suite doubles as the
nowcast target/constraint set:

1. **Scale final demand** per region × category, and per commodity family
   where physical benchmarks exist — a luxury of the hybrid units: IEA energy
   balances (TJ, same units as the table) for energy carriers, FAO food
   balances for food, apparent-consumption indices for materials; real
   GDP/consumption growth (WDI/AMECO) as the fallback scalar.
2. **Recompute** X, VA, E through the Leontief closure (MARIO: scaled `Y` via
   `update_scenarios` or a Percentage shock on `Y`).
3. **Benchmark ex post** — same WP6 suite, now used as targets — and
   reconcile conflicting constraints with GRAS/RAS. Note: MARIO has a RAS
   balancing API on the unmerged `dev_gtap` branch; reconciling that branch
   is part of this work package.

Properties: composition and level updates commute (mixes preserve column
totals, Y scaling scales columns), so the order composition → levels →
reconciliation is a convention, not a constraint. Document explicitly that
technology recipes (`u`) and per-activity emission intensities stay at 2011
wherever no mix is updated — the same philosophy as EXIOBASE's own
extrapolated years and GLORIA nowcasts.

### WP8 — Release & versioning

- v1.0 = supply mixes only; v2.0 = + electricity trades (existing).
- **v3.0 = P1 energy-chain trades + mixes, shipped with the first benchmark
  report (WP6 families 1, 2 and 5 at minimum) and with its raw inputs
  governed in nxbase (at minimum the two retrofits: Electricity Maps trades
  and EMBER).**
- v3.x = P2 material chains as adapters land, benchmark report extended.
- v4.0 = + nowcast levels (WP7).

## 4. Conventions

- Pooled labels: `"{commodity} - supply"` / `"{commodity} - need"` (MARIO
  defaults; recorded in `db.meta.pooled_trade_map` — always read them from
  there, never hardcode).
- Trades input: `support/trades_{year}.xlsx`, one sheet per commodity,
  origins×destinations matrix, columns summing to 1 over the listed origins.
  Legacy shock-format workbooks are pivoted on the fly by the notebook.
- Raw-data governance: new raw inputs enter through nxbase (source +
  parser, see WP0), never as new loose files; the pipeline reads nxbase
  through the query API (`support/nxbase_client.py`, provenance logged per
  run). "Never fetch live data" keeps applying to internet sources —
  governed nxbase is the legitimate exception.
- Language: this repo and everything written into nxbase records (shorts,
  names, set contents, commit messages) are in **English**; the nxbase
  knowledge base is in Italian.
- Set `db.meta.source` to a string containing "EXIOBASE" right after parsing:
  it enables the RoW region expansion in the EMBER (and future) adapters.
- Scenario names: `baseline` = updated mixes (v1.0 content), `ee_trades` = +
  updated trades. New scenarios per data vintage rather than overwriting.
- Requires MARIO ≥ the `dev` branch with `update_supply_mix`,
  `update_trade_mix`, `pool_trade` (see MARIO CHANGELOG, *Unreleased*).

## 5. Open decisions

- [ ] Pooling perimeter: electricity only, +gas, +fuels? (proposal: minimal,
      extend when a use case demands the market-share view)
- [ ] Domestic share for energy carriers: IEA balances see production, so
      the full origin mix (domestic + imports) is updatable for P1 — update
      the domestic split in v3.0, or stay import-only like the materials?
- [ ] GWP set: AR4 (25/298, current v2.0 convention) vs AR6 (29.8/273, used
      for the raw-table runs). nxbase already governs AR4/AR5/AR6 baskets
      and exports them via `export-mario-ghg` — proposal: move the
      validation footprints to AR6 consumed from that export.
- [x] nxbase↔pipeline interface — **closed (2026-07-13)**: query API via
      the `support/nxbase_client.py` client module; no materialized export
      files; provenance (nxbase version + source vintages) logged per run.
- [ ] LCA reference set for technology footprints (WP6.3): UNECE 2021 vs
      IPCC AR5 Annex III vs ecoinvent (licensing!); ranges or point values.
- [ ] Benchmark scope gating v3.0: families 1+2+5 only, or also 3
      (technology footprints)?
- [ ] BACI vintage policy for P2: pin one release per database version?
- [ ] Nowcast target year and benchmark set — deferred with WP7, revisit
      after v3.0.
