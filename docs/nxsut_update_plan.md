# nxsut update — master plan

**The entry point.** Consolidates every decision taken on bringing nxsut from
its 2011 technology base to the present (target year **2023**), as of
**2026-08-01**. Detail lives in the linked companion docs; this document owns
the goal, the pipeline order, the status, the decision log and the build
sequence.

Companions: [tech_coefficient_update_plan.md](tech_coefficient_update_plan.md)
(coefficients, volumes, step 0, Merciai balance mapping) ·
[nowcast_lp_cvxlab_draft.md](nowcast_lp_cvxlab_draft.md) (the reconciliation
LP, validated) · [transport_service_layer_plan.md](transport_service_layer_plan.md)
(the transport module, built first) · nxbase KB `nxsut_bridge.md` (Tracks A-D:
the governed data layer).

## Goal

nxsut 3.x is EXIOBASE Hybrid 3.3.18 (base year **2011**) rebalanced through an
open-data MARIO pipeline. The update brings the table to **2023** in three
respects, in decreasing order of priority:

1. **Technology** — the energy dimension of every activity's recipe (fuel
   switch), observed from energy balances; emissions recomputed bottom-up
   (fuel × EF), no longer frozen 2011 coefficients.
2. **Structure** — supply/trade mixes already updated (electricity, steel,
   aluminium, Isard commodities); **transport rebuilt as a service layer**
   (the one structural addition promoted into the update, by decision).
3. **Levels** — activity outputs, final demand, value added reconciled to
   observed 2023 anchors and GDP/VA, via a per-country LP.

**Principles** (constant throughout): open data only (IEA avoided); physical
balances are the hard skeleton (identities exact, observations elastic);
verify-before-assert (every endpoint/license tested before use);
**govern-native in nxbase** (sources kept faithful, mapping via the Rosetta
graph), consume via API/graph; deterministic updates for what has exact data,
optimization only for what is genuinely over/under-determined.

## Where we stand

- **v3.0 shipped** (2026-07-18): first fully-open-chain nxsut (EMBER supply
  mix + ENTSO-E electricity trade), imported in nxbase (`NXS30.*`, fc+fa,
  published open).
- **v3.1 in development** (2026-07-31): material trade update from **BACI**
  — steel + aluminium **pooled** (Chenery-Moses `need`/`supply`), **Isard**
  update for chemicals nec / N-fertiliser / non-metallic minerals /
  non-ferrous metals, selected by the **pooling KPI** (materiality X·f ×
  heterogeneity P90/P10); BACI full table (10.9M rows Y24) local in nxbase
  with client file-fallback. Measured effect: consumed-vs-produced footprint
  ±30% by country.
- **Nowcast designed and mechanically validated** (2026-08-01): the LP solves
  end-to-end on cvxlab (toy instance, HIGHS, every mechanism exercised);
  the data layer for it (UNSD energy balances) is governed and imported.
- **v3.2 BUILT — the first integrated vintage** (2026-08-02, year 2023):
  full gen_v3 run with the **transport service layer** (Moves B+A+C: the
  commercial transport sectors split into freight/passenger children in
  tkm/pkm, private mobility as household-operated vehicle activities,
  own-account freight externalised) and the **UNSD-first supply mixes**
  (172 of 199 country-years from UNSD.GEN, EMBER as arbiter/fallback).
  Grid 48 x **207 activity x 211 commodity**, exported to `nxsut/v3.2/2023`
  with a detailed readme; the layer covers road, rail, water and air.
  Acceptance in `transport/validate_v32.py`: every transport activity
  present; electricity anchors land on **2023** values (IT 334, DE 361,
  FR 86, PL 688 gCO2eq/kWh) and the BEV footprint follows them down to
  49 g/pkm — the mix update propagates into transport as designed.
  The SUT perimeters now match the UNSD balances, which is what the
  nowcast LP needs to bind its fuel bands.

## The update pipeline (run order)

Everything upstream of the LP is a **deterministic prior transformation**;
the LP closes; emissions recompute last. Status legend: ✅ done · 🔧 designed ·
⬜ to do.

| # | stage | detail | status |
|---|---|---|---|
| 0 | Prior | nxsut 3.1 table (BFG/OFG realloc, pooled ELE/steel/alu, Isard, ENTSO-E+BACI mixes) | ✅ |
| 1a | Supply mixes & routes | electricity mix **UNSD-first, EMBER arbiter** (step 0 run: 173 UNSD / 32 EMBER); Ghezzi steel routes | ✅ (v3.2) |
| 1b | Trade mixes | ENTSO-E (electricity), BACI (materials); extension to *all* tradable goods pending | ✅ / ⬜ ext. |
| 1c | Autoproduction netting | **closed as a no-op (2026-08-03, verified on the table)**: no non-energy activity supplies electricity in v3.2 — EXIOBASE routes all generation through the power columns. D9 survives only as the anchor perimeter: power `x_obs` = **total** generation (main+auto ≡ the blend), never `015x`-only. No rebuild needed | ✅ no-op |
| 1d | **Transport service layer** | Moves B (split commercial) + A (private mobility MIMO) + C (own-account externalised); NXTR.V0 recipes governed | ✅ (v3.2) |
| 2 | **LP nowcast** (cvxlab) | per (region × year={2023}) grid; energy-carrier rows free, L1 relative weights, elastic bands, GDP/VA closure; world-balance audit | 🔧 toy-validated · reviewed vs v3.2 (D12–D18) |
| 3 | Emission recompute | bottom-up fuel × **EF-by-fuel (IPCC 2006, governed like GWP)**; carbon mass balance on ~10 feedstock sectors | 🔧 |
| 4 | Validation | step-0 UNSD↔EMBER; implied efficiencies/economies; EDGAR + Climate TRACE radar; CRF `1.A.3.b` transport split; world trade audit | 🔧 |
| 5 | Publication | licensing per source; promote `WSTEEL`; nowcast table as new NXS vintage | ⬜ |

## The data layer (governed in nxbase)

| source | content | state |
|---|---|---|
| `EMBER.GEN25` | generation TWh by tech × country × year | ✅ open |
| `ENTSOE.IMX.Y23-25` | electricity import mix (NET, A09) | ✅ public |
| `BACI.Q.Y23/Y24` | bilateral trade, **full** (11 229 391 + 10 886 196 rows, all HS chapters; Y23 = the EXP anchors of the target year) | ✅ local (+client file fallback) |
| `UNSD.USE` | fuel use × IRES sector × country, 2021-23 (53 451 rows; SIEC/IRES native, NXB bridges, **incl. bunkers 051/052** — verified on the data: 051 marine, 052 aviation) | ✅ open |
| `UNSD.CON` | household final consumption (IRES 1231, stationary), parameter CON (4 392 rows) — the residential Y anchor + the D14 stationary term | ✅ open (2026-08-03) |
| `EX3102m.ixi.VA.Y21-24` | EXIOBASE 3.10.2 monetary value added by factor × industry (matrix V; Y23 = 35 235 rows, IT 2023 = 1.96 T€ ≡ GVA) — the VA_tgt panel, GDP closure same-source | ✅ local (2026-08-03; Y21/22/24 registered, import on demand) |
| `USGS.MCS25` | USGS Mineral Commodity Summaries world production 2023 (89 series, 1 025 rows, public domain) — the industrial x_obs anchors; **replaces UNSD ICS** (open mart frozen at 2016) | ✅ open (2026-08-03) |
| `NXS3` set rows for the v3.2 grid | 15 transport activities + 10 physical commodities + pooling twins/pools — B_ires can walk the graph | ✅ (2026-08-03) |
| `UNSD.GEN` | generation by source/plant-type/producer (`01x/015x/016x` — CHP, waste, main/auto), 12 678 rows, parameter `SUP` | ✅ open (2026-08-01) |
| `ECB.FX`, `WB.DFL` | FX + GDP deflators (VA-target temporal alignment) | ✅ public |
| IPCC GWP AR4/5/6 | governed factors | ✅ |
| EF-by-fuel (IPCC 2006) | combustion CO2/CH4/N2O per SIEC fuel | ⬜ kit |
| Eurostat `nrg_bal_c` | EU balances, high quality (SIEC/IRES twin of UNSD) | ⬜ kit |
| `ITF.PASS/FREIGHT/TRAFFIC/FUEL` | pkm/tkm/vkm + fuel deliveries, ~56 countries, native Mpkm/Mtkm/Mvkm (17 234 rows; hire vs own-account observed worldwide) | ✅ open (2026-08-01) |
| `ESTAT.ROADPA/RAILPA/ROADGO` | EU quality layer: pkm by vehicle type, tkm by hire/own-account (4 922 rows; vkm & tonnes native in snapshot = load factors) | ✅ open (2026-08-01) |
| `ESTAT.SBSH49` · `ESTAT.ROADGOODS` · `ESTAT.CARPARK` | Move-B monetary split key (SBS turnover, 2 283 rows) · own-account propensity by goods (snapshot) · car fleet by motor energy (snapshot) | ✅ open (2026-08-02) |
| `NXTR.V0` | transport recipe inventory: 14 vehicle techs, intensities + service yields (1 155 rows) | ✅ open (2026-08-01) |
| UNSD flow `06`, FAO FBS | stock changes (needs a stock-change parameter — tree design decision, proposal: child of `STK`), food anchors (volumes) | ⬜ recipes |
| GTAP elec. prices | price cross-check | ⬜ local source |
| WDI + EDGAR | benchmark KPIs (GDP/GVA; emissions by sector) — `EMBER.CI25` already governed for KPI 3 | ⬜ kits |
| Eurostat `nrg_bal_c` | EU quality twin of UNSD.USE (same SIEC/IRES namespaces) | ⬜ kit |

## Aggiornamento del layer dati (2026-08-03)

Nuove source governate, tutte `open`, tutte con pull snapshot-first:

| source | cosa dà | stato |
|---|---|---|
| `UNCTAD.FLEET` | portata della flotta per **proprietà effettiva** — la chiave di residenza marittima; primo uso del nuovo parametro `STK` | ✅ open |
| `UNCTAD.SEABORNE` | tonnellate caricate per anno: porta il livello IMO all'anno costruito | ✅ open |
| `IMO.GHG4` | lavoro marittimo mondiale 2018 (Fourth IMO GHG Study, tab. 71), unità nativa `Mtnm` | ✅ open |
| `IPCCGL.EF` · `IPCCGL.NCV` | fattori di emissione da combustione e poteri calorifici IPCC 2006, 33 combustibili; primo uso del nuovo parametro `ncv` | ✅ open |

Due estensioni del contratto dei parametri in nxbase, entrambe per colmare
buchi reali e non casi particolari:

- **`STK` (Stock)** — l'unico parametro che descrive uno *stato* e non un
  flusso. Serve anche a capacità elettrica installata, parco veicoli, stock
  edilizio; finora quelle fonti restavano registrate ma non importate;
- **`ncv` (Net calorific value)** — energia per unità di commodity, stessa
  forma di `prc`. È il fattore di conversione massa↔energia che la KB elenca
  da sempre e che non aveva un posto: serve perché l'IPCC pubblica i fattori
  di emissione **per unità di energia**, mentre la tavola è in tonnellate.

## Decision log (consolidated)

**2026-08-03 (pm)** — **LP draft reviewed against the built v3.2** (draft
§D12–D18): grid constants from the table (48 × 201 × 205; `fuels` = ~55
SIEC-mappable carrier rows incl. both pooled electricity rows, nuclear fuel
exogenous); pool activity columns masked out of `B_ires` (plumbing, not
consumption); transport bands final form — road regains a **reduced,
observed Y term** (`1221 + 1231_mf` combined target; the D11 retirement was
too absolute), air/sea bands include bunkers `051/052` (residence), children
get pkm/tkm `x_obs`; **netting (D9/WS-NET) must land before the pilot**
(v3.2 rebuild); `NXS3` namespace extension in nxbase (15 activities + 10
commodities) so `B_ires` walks the graph; VA targets from a new local
`EX3102m.VA` source (existing `VA` parameter + `VA.*` flows), **GDP closure
v1 = Σ VA_tgt same-source**, WDI benchmark-only. Data build order: pilot
critical path = NXS3 ext → UNSD ext (051/052, flow 06, `1231`→CON) →
BACI.Q.Y23 → EX3102m.VA → WS-NET+rebuild → bridge; coverage wideners after
(UNSD ICS first, then WDI/EDGAR benchmarks, `nrg_bal_c`, FAOSTAT).

**2026-07-31** — BACI governed native (`TRD`, `HS22`→CN26, ETALAB); pooling
KPI = materiality × heterogeneity, gate = physically-traded goods; pooled =
ELE/steel/alu, Isard for 4 more; BACI storage = local + file fallback (never
hosted); full-table import via the nxbase bulk path.

**2026-08-01** — the design day:

- **UNSD layer**: detailed Energy Statistics DB (75 SIEC × 216 IRES × 251
  areas, SDMX, license `UNDATA` verified open) governed native; 6 NXB
  manufacturing bridges (ISIC 2-digit groupings) with NACE re-parents; heat
  merged on the pre-existing `NXB | Steam and hot water` (HWAT re-anchored).
- **Nowcast LP** (all in the draft, D1-D10): grid per (region×year) starting
  `{2023}`; only **energy-carrier rows** of U endogenous (incl. electricity
  and heat→`HWAT`); **L1 with relative weights** (1% costs the same across
  t/TJ/MEUR); observation **masks** (not-reported ≠ zero); **EXP anchored to
  observed BACI**; inventory anchors from UNSD flow `06`; VA targets =
  EX3.10.2 (reaches 2024) by macro-group, **GDP closed production-side**
  (prices = optional cross-check only); **prior = the post-deterministic-
  update table** (mixes never redone by the LP, they re-enter as elastic
  anchors); global behaviour **audited** (world balance per commodity +
  optional Gauss-Seidel sweep); Merciai eq. 15 (power efficiency)
  **satisfied by construction** once both balance sides are UNSD-constrained
  — the explicit band is retired as redundant, kept only as a dormant
  one-sided-data guard + step-0/post-solve diagnostic.
  **Toy-validated end-to-end on cvxlab 1.0.1** (HIGHS; masks/weights
  corrections found and absorbed; toy in `nowcast/toy_model/`).
- **Merciai balance mapping**: eq. 12 ↔ LP identities; eq. 13 (satellite
  mass balance) ↔ combustion-based recompute + carbon-balance radar (full
  multi-layer out of scope v1, declared); eq. 15 ↔ implied by construction
  (D10 retired to dormant guard, see LP draft).
- **Electricity source hierarchy — UNSD-first, EMBER-as-arbiter** (late
  addition): wherever step 0 finds UNSD ≈ EMBER, **UNSD becomes the primary
  source for the generation mix too** (not only the use side): it carries
  the **CHP plant-type split** (`015CC/CE/CH` + autoproducer twins — the
  Merciai-consistent structure EMBER cannot see), **waste-to-energy
  separated** (`01RW/01NRW`), finer by-fuel thermal detail (incl. `01MG`
  manufactured gases = BFG/OFG electricity) and the **main/autoproducer
  split** feeding the netting. EMBER is demoted to **arbiter** (where UNSD
  diverges or under-reports) **and timeliness** (2024+, monthly). Step 0
  becomes the per-country *source selector*. New (cheap) brick: sibling
  recipe **`UNSD.GEN`** on the same snapshot (production transactions —
  already pulled, no new fetch).
- **Transport**: the **mode-vs-user mismatch** named as the root issue
  (`1221` = hauliers + own-account + private cars; `1231` excludes
  transport); target = **service layer** (inter-modal `Mobility`/`Freight`
  needs via nxbase `need`+`mkt`, vehicle technologies, fuel-economy recipes
  — the electricity pattern; MIMO as cvxlab template); **sequencing
  decision: built FIRST**, before the first production nowcast (D11 bucket
  fallback retired unused); data endpoints verified live (Eurostat incl.
  own-account freight split; ITF 48 countries incl. China).

## Build order (workstreams)

1. **WS-T — Transport service layer** — **DONE 2026-08-02** (v3.2 built)
   1. ~~nxbase governance kits: ITF + Eurostat transport~~ **DONE
      2026-08-01** (22 156 rows open; cross-source check ITF ≡ ESTAT).
   2. Taxonomy + recipe table v0 — **global, 14 techs** (decided: one gas
      car tech, hybrids folded into G/D; MIMO household-car convention;
      Odyssee occupancy; recipes governed in nxbase alla Ghezzi) — schema
      under review (brick 2a), values next (brick 2b).
   3. `add_sectors`-class prior transformation; first acceptance check on a
      data-rich region, then all — acceptance = `1221` band closes.
   4. Population waves: observed countries → RoW proxies (stock × mileage ×
      GFEI economy).
2. **WS-0 — Step-0 script** — **DONE 2026-08-02** (selector + implied
   efficiencies + `UNSD.GEN`; arbitrated blend live in the client).
3. **WS-EF — EF-by-fuel kit** — **DONE 2026-08-03** (`IPCCGL.EF` +
   `IPCCGL.NCV` governed, consumed by Moves A/C).
4. **WS-CON — households recipe** (`1231`→`CON`) + **Eurostat `nrg_bal_c`**
   twin (EU quality upgrade on the same SIEC/IRES namespaces).
5. **WS-NET — autoproduction netting** implementation (D9, gen_v3).
6. **WS-LP — real model dir + bridge** (nxbase/MARIO → sets+inputs), IT×2023
   pilot solve; then the 49-region grid. *(After WS-T lands, per decision.)*
7. **WS-VOL — volumes anchors** (FAO FBS pull, flow `06` stocks, Y priors).
8. **WS-TRD — all-commodities Isard** in gen_v3 (enabled by full local BACI).

Then: **full 2023 run → validation loop → publication**.

## Open points

- **Repo governance**: `docs/` + `nowcast/` are untracked — public docs vs
  internal (gitignore) still to decide; nxbase `feat/unsd-energy` heat-fix
  commit pending ok.
- Per-doc open questions: transport doc (5: household-car convention, load
  factors, tech granularity, `122x` electricity, business travel); LP draft
  (slice-ordering assert, solver, grid-vs-global quantification).
- Smaller: LU/CY control-area fetch (ENTSO-E); HFC/PFC whitelist re-imports
  (nxbase backlog); GFEI/ICCT redistribution licensing to verify.
- **UNSD conversion factors → governed LHV parameter (queued, decided
  2026-08-02)**: the snapshot's `CONVERSION_FACTOR` column (NCV per SIEC
  commodity × country × year) is the first native feed for nxbase's
  deferred **cross-magnitude conversion branch** (mass↔energy via LHV,
  mass↔volume via density — the Luca Pint contexts). Import as
  parameter + data rows (GWP/FX pattern) once current points close;
  `nowcast/step0_implied_efficiency.py` reads the snapshot meanwhile and
  switches to the API when governed. Mirrored in nxbase KB
  (`luca_unit_conversion.md`).
