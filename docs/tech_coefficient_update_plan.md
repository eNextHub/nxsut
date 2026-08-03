# Plan — updating nxsut's technical & emission coefficients

> Part of the **nxsut update master plan** — see [nxsut_update_plan.md](nxsut_update_plan.md) for the pipeline order, status and build sequence.

Roadmap for bringing the EXIOBASE Hybrid v3.3.18 **base year 2011** technology up
to the present. This is the hardest and highest-value update beyond the trade
mixes; captured here so we can pick it up deliberately.

## Why coefficients first (and what "volumes" are for)

Footprint **intensity** — the flagship nxsut output (kgCO2eq per kWh, per t of
steel) — is `e · (I − A)⁻¹`: it depends **only on the coefficients** (`A`) and
the satellite (`e`), **not on final demand**. Final demand (volumes) only scales
the **totals** (consumption-based accounts, macro scenarios): `total = intensity
× demand`.

So there are two updates with different priorities:

| Update | Drives | Priority |
|---|---|---|
| **Technical + emission coefficients** (this plan) | intensities | high |
| **Volumes / final demand** | totals & scenarios | separate, lower |

*Volumes note:* a separate, lower-priority track (it drives totals & scenarios,
not intensities) — detailed in **Volumes — final demand** at the end. RAS lands
in MARIO ≥ 1.1.0.

## Scope — nowcast vs disaggregation (2026-08-01, discussed with Nicolò)

Two planes, kept separate:

- **Nowcast (this plan)**: update the *existing* sectors' coefficients, trade
  and levels to the target year. Key nuance: for existing sectors the **fuel
  rows need no technology inventories** — the energy balances *are* the
  observed physical recipe of the energy dimension (t/TJ of each fuel per
  sector per country per year), which is exactly the data monetary tables
  lack. That is why the fuel switch is the first updatable physical
  coefficient block.
- **Disaggregation (separate track)**: *adding* sectors — most wanted:
  **private transport** and **private heating** (transition-critical). This
  does need new technology recipes (the Ghezzi/add_sectors pattern); the
  monetary split machinery (split_sectors / KL) does not transfer as-is to
  hybrid units. Parked, but the UNSD layer already carries its data:
  residential heating = balance flow `1231` by fuel (in the governed
  snapshot, pending the `CON` recipe), transport = flows `122x`.

  **Transport — the mode-vs-user mismatch (2026-08-01, Lorenzo)**: beyond
  any disaggregation, energy and economic accounting are structurally
  incoherent on transport. Energy statistics classify by **mode**: `1221`
  road is *all* road fuel — the transport industry (H.49), every other
  sector's **own-account logistics**, and **households' private cars** —
  while `1231` residential *excludes* transport (stationary use only). The
  economic table classifies by **user**: H.49 buys only the hauliers' fuel,
  own-account fuel is an input of each industry, household fuel is final
  demand. Consequences for the nowcast: (a) the `122x` buckets must
  constrain the **sum** of the transport activity + own-account users + the
  household motor-fuel Y component (the bucket incidence gains a Y term —
  LP draft D11), with the within-bucket split inherited from the **prior**
  (the EXIOBASE hybrid construction already sectorized transport fuel — we
  inherit Merciai/Stadler's 2011 reallocation); (b) household motor fuel is
  anchored as a share of `1221`, never from `1231`; (c) `1223/1224` are
  *domestic* aviation/navigation — the international part is the separate
  bunker flows `051/052` (in the snapshot), reallocated to resident
  carriers in the prior (residency vs territory; fuel tourism stays an
  accepted v1 error). The genuinely hard residual: **no 2023 observation of
  the within-bucket split** — prior shares persist; future levers are the
  UNFCCC CRF `1.A.3.b` road breakdown (cars / light & heavy trucks /
  buses, Annex-I), vehicle-stock/vkm statistics, and fuel-type heuristics
  (gasoline is household-dominated in most countries). The same levers
  feed the private-transport disaggregation when it comes.

  **Target architecture (v2, Lorenzo 2026-08-01): transport as a service
  layer — the electricity pattern.** The root solution is not a better
  split of the prior but an **activity-based bottom-up rebuild**: transport
  *service* commodities in physical units (**pkm** passenger, **tkm**
  freight), produced by vehicle **technologies** (car-gasoline/diesel/BEV,
  bus, rail, truck classes…) whose recipe is the **fuel economy ×
  load/occupancy factor** — the *simplest* kind of technology inventory
  (one line per tech, not a plant flowsheet), so the "physical recipes"
  barrier is at its lowest exactly here. Fuel use reconstructs bottom-up as
  `Σ tech activity (vkm) × economy`, and the mode-vs-user mismatch
  dissolves by construction (fuel follows vehicle activity, not purchase
  statistics). Crucially, the demand side is an **inter-modal mobility
  need**: a modal-agnostic pkm/tkm *need* served competitively by modes —
  the nxbase `need` level was designed for exactly this (*mobility* is a
  canonical need example) and the `mkt` parameter is its market-share
  grammar; modal shift becomes a first-class scenario lever, like the
  electricity supply mix. The **MIMO cvxlab model is the in-family
  template** (`light_transport_hh`/`light_transport_serv`/`heavy_transport`,
  activity in `MVkm`/`MVkm-ton`, vehicle stocks as capacity). **Data map
  (verified 2026-08-01)**: pkm/tkm — Eurostat (EU, open API), **ITF/OECD**
  (~60 countries, all modes, series to year-1, open with attribution),
  UNECE (pan-Europe/CIS); fuel economy — **GFEI benchmarking** (latest
  2019-2022) and **ICCT** market statistics (report-grade), **EEA CO2
  monitoring** of new registrations (EU, fully open); stocks — OICA (free);
  vkm outside the EU is the weakest link. **Global-south gap accepted and
  closed by construction**: where surveys are missing, the prior is stock ×
  default mileage × GFEI economy, and the observed `1221` country total
  (already governed via UNSD) remains the reconciling band — bottom-up
  structures the split, the balance closes it. **Sequencing — DECIDED
  2026-08-01 (Lorenzo): the transport layer is built FIRST** ("no rush,
  anticipate what conceptually comes first"): it is a prior transformation,
  so it slots upstream of the LP, and the first production nowcast then
  constrains the UNSD balances against the right structure (the D11
  fallback in the LP draft is retired unused; transport enters via observed
  vkm/pkm `x_obs` anchors). Full design, verified data endpoints and
  deliverables: [transport_service_layer_plan.md](transport_service_layer_plan.md).
  IEA MoMo remains the closed gold standard we deliberately avoid.

## Approach — bottom-up, combustion-based (physical-native)

Move emission accounting from fixed per-sector coefficients to **computed**
combustion CO2 = `fuel_burned × EF_fuel`. Emissions then become a function of the
(updatable) fuel-use structure, which is exactly what enables the **fuel-switch**
update. EXIOBASE Hybrid already carries the physical fuel inputs in the use
matrix, so "fuel burned" is largely already there — you apply the EF instead of
the frozen 2011 emission coefficient. Direction of travel: EXIOBASE 3.9+, BONSAI.

We already do sector-specific versions of this: the **EMBER** electricity supply
mix, the **Ghezzi** steelmaking routes, and the **BACI** trade mix (sourcing
coefficients). The general update systematises them.

**Combustion activities** (BONSAI's fictitious combustion sectors): **not
adopted.** Clean emission allocation is a plus, not a necessity; it still needs
the combustion fraction (so it doesn't solve burned-vs-transformed), and it adds
structural complexity. Adopt the bottom-up *computation*, skip the restructuring.

## Emission factors by fuel — governed like the GWP factors

CO2 EF is ~fuel physics (carbon content × oxidation) and essentially
**location-invariant** — how much CO2 a kg of coal makes barely depends on where
it burns — so **IPCC 2006 defaults** (global averages) suffice (CH4/N2O vary a
little by combustion tech; IPCC defaults are fine). This fits the nxbase pattern
exactly: an **EF-by-fuel `parameter` + `data` rows**, just like the governed GWP
factors — reusable, no hardcoding. **First concrete brick** (small, independent).

## Burned vs transformed — carbon mass balance, not a convention

The hard part is: an activity's fuel input can be **combusted** (→ CO2) or used as
**feedstock/reductant** (→ carbon embodied in product, no combustion CO2 there).
Relying on the energy-balance convention (energy use vs non-energy use vs
transformation) to decide this per sector introduces real uncertainty.

The more robust framing is a **carbon mass balance**: don't ask "burned?", track
the carbon —

    C_in (fuels + feedstock) = C_in_products + C_emitted + C_stored/waste
    ⇒ C_emitted = C_in − C_in_products − C_stored

Carbon leaving in **products** is transformed (not emitted); the rest is emitted.
Natural for a **physical** table (the in/out flows are already there; add C-content
coefficients — for fuels these are the EF, for products, e.g. coke/plastics/
bitumen, they are known). The convention-uncertainty becomes a mass-balance
**residual (≈ 0 expected)** that is checkable and self-diagnosing.

The uncertainty is **concentrated** in ~5–10 transformation/feedstock sectors —
refineries, coke ovens, **blast furnaces**, petrochemicals, cement (+ the
non-combustion **process CO2** from calcination, a separate source). Carbon-
balance those; clean-combust the rest. The hardest case — **steel BFG/OFG** — is
already handled via the blast-furnace-gas reallocation (a precedent to reuse).

## Data — bottom-up fuel use (open, SDMX)

Fuel use by sector × country × fuel:

- **Eurostat `nrg_bal_c`** — EU + EEA, detailed. Open, **SDMX API**.
- **UNSD Energy Statistics** — **251 areas** (to 2023), open, **SDMX REST API**
  (verified 2026-07-31). *Not* coarser than IEA structurally — same IRES/SIEC
  basis: **75 SIEC products** (coal split anthracite/coking/lignite…, oil split
  gasoline/diesel/fuel-oil/naphtha/pet-coke…) and **216 IRES transactions**, incl.
  the ~13 industry sub-sectors under *Final energy consumption* (iron & steel
  `1211`, chemical & petrochemical `1213`, non-ferrous `1214A`, non-metallic
  minerals `1214B`, transport equipment `1214C`, machinery `1214D`, mining
  `1214E`, food `1214F`, paper `1214G`, wood `1214H`, construction `1214I`,
  textile `1214J`, nes `1214O`), transport modes `122x`, and **households `1231`**
  (the residential Y anchor); plus transformation `08x`, energy own-use `09xx`,
  and **non-energy uses `11`** (feedstock — the burned-vs-transformed key). Native
  **physical units** (incl. metric **tonnes**, not only TJ). Fills the non-EU gap.
- **EMBER** — power-sector fuel mix (the single biggest lever), already governed
  and used for the electricity supply mix.
- *IEA World Energy Balances* — the gold standard but **proprietary** → breaks the
  open pipeline; avoid (the nxbase "first restricted case").

**UNSD SDMX access (verified 2026-07-31):** REST at `https://data.un.org/WS/rest/`
— DSD + all codelists via `datastructure/UNSD/DSD_Energy/?references=all`; data via
`data/DF_UNDATA_ENERGY/{FREQ}.{REF_AREA}.{COMMODITY}.{TRANSACTION}` (dimensions in
that order; `REF_AREA` = M49 numeric, `FREQ=A`). Two gotchas found by testing:
`startPeriod`/`endPeriod` query params **500 the server** (NSI-web-service bug) →
omit them and slice time client-side; a few areas are **merged** (`382` = *Italy
and San Marino*) → a small country concordance to EXIOBASE regions is needed. Same
SDMX-RI backend as Eurostat, so one SDMX client serves both.

Ingest via the nxbase **API-first / snapshot-first** pattern (like the ECB FX and
World Bank deflator pulls): SDMX pull → snapshot in `nxbase_raw` → parser →
governed source; the consumer recomputes with the governed EF.

## Validation — top-down as a radar (not a replacement)

Cross-check the resulting sector emissions against open global inventories:
**EDGAR (JRC)** (by IPCC sector × country × gas, to ~2022) and **Climate TRACE**
(asset-level). Where bottom-up diverges from the inventory, the burned/transformed
split or the sector concordance is probably wrong there → an automatic flag on the
problem sectors.

**Success test:** footprints move toward known-good references *where the base was
anomalous* (e.g. India electricity ~2× Electricity Maps → normalising is a
confirmation, not a bug) and stay stable where the base was already fine — not
"footprints don't change".

## The real work (where the effort goes)

- **Concordances** — energy-balance fuel flows ↔ EXIOBASE energy commodities;
  EDGAR IPCC sectors ↔ EXIOBASE activities.
- The ~10 transformation/feedstock sectors (carbon balance + process CO2).

## Sequencing

0. **UNSD ↔ EMBER coherence check** (step 0 — runnable now, no new pulls).
   The two datasets overlap on electricity and must not disagree silently:
   compute the generation mix per country/year from the UNSD snapshot
   (production transactions `01`/`015x` + the by-source commodities
   `7000G/H/N/S/W…`) and compare with EMBER. Where they are close, use UNSD
   on the use side for **internal coherence** (same source both sides of the
   balance); where they diverge, **trust EMBER** for the mix. Bonus
   diagnostic: UNSD `088x` gives the fuel *inputs* to power plants, EMBER
   the *output* by tech → **implied efficiencies** per country, a
   quantitative arbitration criterion (and an early radar on bad country
   data) instead of a judgment call. Step 0 also decomposes generation into
   **main-activity vs autoproducers** (UNSD `015x` vs `016x` families, incl.
   `016SP` rooftop-PV autoproduction; `08811/08812` inputs): the netted
   nowcast table anchors `x_power` to the `015x` main-activity side, so
   EMBER totals must be split accordingly (see the autoproduction-netting
   decision in the LP draft, D9). **Step 0's output is a per-country source
   selection (decided 2026-08-01, Lorenzo): UNSD-first wherever UNSD ≈
   EMBER — including the generation mix itself**, because UNSD carries what
   EMBER cannot see: the CHP plant-type split (`015CC/CE/CH`, Merciai-
   consistent), waste-to-energy separated (`01RW/01NRW`), finer by-fuel
   thermal detail (incl. `01MG` manufactured gases = BFG/OFG electricity)
   and the main/autoproducer split. EMBER remains the arbiter where they
   diverge, and the timeliness source (2024+). Implementation: sibling
   recipe `UNSD.GEN` on the same snapshot (production transactions already
   pulled).

   **STATUS: RUN (2026-08-01).** `UNSD.GEN` is governed and imported
   (nxbase `5755c6d`: 68 IRES production activities, parameter **SUP** —
   data-driven revision of the approved OUT: CHP plant types are observed
   with two products, 7000 electricity + 8000 heat; 12,678 rows, 0 skips;
   IT 2023 validation: net 256.6 TWh ≈ Terna, Solar PV main+auto = 30.71
   TWh **exactly** equal to EMBER). The selector
   (`nowcast/step0_electricity_source_selector.py` →
   `nowcast/step0_selection.csv`) compares the 9-family mix per country on
   the latest common year (TVD on shares decides — the consumed object is
   the mix, levels are reconciled by the LP anchors; dTOT>0.25 only flags):
   **208 countries compared → 139 UNSD (all big emitters: IT tvd 0.004,
   ES 0.003, PL 0.005, GB 0.006, FR 0.010, US 0.012, DE 0.016, CN 0.018,
   IN 0.044), 18 EMBER, 51 REVIEW** (mostly small systems; JP the one big
   REVIEW at 0.062). The CHP payoff is measured: share of thermal
   generation from CHP plants = PL 0.96, IT 0.60, FR 0.43, DE 0.40,
   ES 0.26 — invisible in EMBER, load-bearing for heat/CHP accounting.
   Family mapping declared in the script (by-fuel view for thermal
   families, source totals for non-thermal, hydro net of pumped storage,
   other/chemical sources → Other Fossil).

   **Implied-efficiency arbiter — RUN (2026-08-02)**
   (`nowcast/step0_implied_efficiency.py` → `step0_efficiency.csv`): fuel
   inputs to plants (088 total + 0881x/0882x/0883x by plant type, energy
   via the snapshot's native CONVERSION_FACTOR column — the reason this
   reads the governed snapshot directly; DG/DS geothermal/solar heat and
   0889E/H electricity inputs excluded; 0100/0200 aggregate-vs-leaf dedup)
   ÷ combustible outputs (015C/016C electricity + heat). Sanity is
   textbook: IT η_tot 0.483 (CHP 0.51), DE 0.459 (CHP 0.64), US 0.437,
   CN 0.495, JP 0.417, GB 0.470 — all in fleet band. Mechanical
   arbitration of the REVIEW pool (plausible η = internally coherent UNSD
   balance → UNSD; η outside bands or >1 → EMBER): **final selection 173
   UNSD (136 direct + 37 η-upgraded) vs 32 EMBER (18 + 14 η-rejected)**;
   hydro-only countries with no combustible fleet keep their selector
   decision. The radar also flags UNSD-selected countries with plant-type
   misallocations (e.g. BR elec-plants 0.155 with CHP 0.939 — bagasse
   accounting; TN CHP 1.147 — impossible, input misreport): usable at the
   9-family level, treat their plant-type split with care.

   **By-fuel resolution (added 2026-08-02)**: the same ratio computed per
   fuel family — inputs = 088 commodity detail grouped
   coal/gas/oil/bio/mgas/waste/peat/oil-shale, outputs = the ``01<fuel>``
   view on 7000T/8000T; both an elec-only and a total (elec+heat) η per
   fuel. Convention-free by construction: renewables and nuclear never
   enter the ratio (no fuel input in 088) — no IEA primary-equivalent
   conventions (33% nuclear, 100% renewables) are needed anywhere.
   Sanity vs the textbook: coal elec-only IT 0.36 / US 0.37 / JP 0.36 /
   GB 0.36 / CN 0.34 (PL 0.26 elec but 0.40 total — the CHP heat
   diversion); gas elec-only IT 0.47 / US 0.45 / JP 0.47 (DE/FR/PL gas
   *total* 0.60-0.66 = cogeneration heat recovery); oil 0.29-0.40. The
   per-fuel flags tightened the arbitration (4 REVIEW countries rejected
   on a broken fuel family).

   **UNSD-based supply-mix path — BUILT (2026-08-02)**
   (`support/nxbase_client.py`): `get_unsd_generation_snapshot()` maps
   UNSD.GEN onto the 9 EMBER family labels (plant-type totals for
   non-thermal, by-fuel view for thermal, hydro net of pumped — the same
   declared mapping as the selector) in MARIO's reduced 4-column format;
   `get_supply_mix_snapshot(years=…)` blends per country on the
   arbitrated selection (UNSD where selected *and* the year is reported,
   EMBER everywhere else — missing-year fallback declared). Validated
   (2023): **172 (country, year) from UNSD.GEN + 27 from EMBER**, grid
   complete (9 families everywhere), IT blend-vs-EMBER TVD 0.006 with
   totals 263.2 vs 261.5 TWh, EMBER-selected countries byte-identical to
   the EMBER path. Remaining integration: gen_v3 switches
   `get_ember_snapshot()` → `get_supply_mix_snapshot()` at the next
   table-generation run (one-line swap, same shape).

   **Coherence with the original table's balance structure (Merciai et al.,
   read 2026-08-01)**: the HSUT construction enforces an *input balance*
   (every input partitions into product/packaging/non-marketable/stock/
   waste/emissions) and a *process balance*; in the balancing module these
   become (eq. 12) product supply=use — covered by the LP's exact
   identities; (eq. 13) the within-activity **mass balance through the
   satellite accounts** (resources, waste, emissions, combusted inputs,
   stock additions, dry-matter coefficients) — deliberately **not** an LP
   constraint: its fuel side is preserved *by construction* by the
   combustion-based emission recompute (satellites scale with fuel use) and
   audited by the carbon-balance residual; the full multi-layer rebalance
   (dry matter, waste fractions, lifetime-function stocks) is **out of
   scope v1**, a declared gap — redoing it means rebuilding Merciai's
   balancing module, not extending the LP; (eq. 15) the power/heat energy
   balance (output ≤ combusted input × cv × efficiency) — **satisfied by
   construction, not by constraint** (revised 2026-08-01): with UNSD-first
   on both balance sides, the use bands (`088x` inputs) and generation
   anchors (`015x` outputs) already confine the implied efficiency; a
   separate band fed by the same balances would enter the same information
   twice. Kept only as a dormant wide engineering guard for one-sided-data
   countries (LP draft D10) and as the step-0/post-solve diagnostic.
1. **EF-by-fuel governed in nxbase** (IPCC 2006; `parameter` + `data`). Small,
   independent, reusable. ← start here.
2. **Combustion recompute** on the *existing* fuel use, carbon-balanced. Validate:
   India-electricity test; mass-balance residual ≈ 0; known-good sectors stable.
3. **Fuel-switch update** — refresh fuel consumption by sector/country from
   Eurostat + UNSD (+ EMBER for power), prioritising high-emitting sectors (power
   ~done → steel, cement, transport, chemicals), the same impact-first spirit as
   the trade-mix KPI.
4. **EDGAR validation loop** on the problem sectors.

Later / separate: **volumes** (final demand) — see the next section.

## Volumes — final demand (separate track)

Lower priority than the coefficients (it drives totals & macro scenarios, not
intensities), but worth structuring — because for some commodities the volumes
can also come **bottom-up and physical**, not just GDP-scaled.

**Bottom-up anchors, where physical statistics exist:**

- **Energy carriers** — the energy balances' *Residential* final-consumption block
  (UNSD flow `1231` *Households*, in native tonnes/TJ) is households' direct
  **stationary** energy demand (heating gas, electricity, cooking fuels),
  physical, per country. **It excludes transport**: households' motor fuel sits
  inside the mode-based `1221` road flow (see the transport note in the Scope
  section) and must be anchored as a *share of 1221*, never from `1231`. It is
  the **same Eurostat/UNSD pull** as the coefficient
  update → *one source, two updates*: the intermediate fuel use feeds the
  coefficients, the residential final consumption feeds Y.
- **Food** — FAO **Food Balance Sheets** (FAOSTAT, open): the *Food* element =
  quantity available for human consumption (tonnes) per country per commodity =
  the household food demand, net of losses/processing (the FBS separates those).
- Most other commodities have no clean physical bottom-up — durables, services,
  and the raw materials (which are overwhelmingly **intermediate**: construction
  materials flow through the construction activity, not to final demand) — so they
  stay top-down.

> **Concrete cvxlab mapping**: see
> [nowcast_lp_cvxlab_draft.md](nowcast_lp_cvxlab_draft.md) — the draft
> `structure_sets` / `structure_variables` / `problem` for this model (fuel
> rows of U endogenous with an L1 prior at endogenous scale, per
> region×year sub-problem grid, elastic observation bands).

**Reconciliation — bottom-up anchors compose with the LP, they don't replace it.**
`GDP = ΣV = ΣY` is an accounting identity; fixing *pieces* of Y (energy, food) and
*pieces* of V (sectors from national accounts) plus the observed GDP total
**over-determines** the system. So the bottom-up anchors enter a **Leontief–
Kantorovich LP** (a second `cvxlab` model, à la `split_sectors`) as **constraints**,
and the LP finds the free Y components + V + output that (a) honour the anchors,
(b) hit the observed GDP and sector value added, (c) satisfy the IO balance
`(I − A)x = y`, minimising deviation from a prior. RAS could balance to the
marginals, but the LP handles the over-determination + inequality constraints
more gracefully — and it lives in `cvxlab`.

**Free residual:** the Y components with no bottom-up anchor and no binding
constraint fall back to a per-country deflated-GDP-growth nowcast (+ Engel-curve
structural shift), then get reconciled by the same LP.

**GDP closure is production-side; prices are a cross-check, not the mechanism**
(2026-08-01, from the price-bridge idea discussed with Nicolò). The LP closes
GDP through the **VA side** (`ΣV_c = GDP_c`, VA targets by macro-group), which
needs no price vector — a sequential price-bridge (physical output × prices,
services as the residual) would be order-dependent and push all the error onto
the last link. Commodity **prices** stay valuable as an *optional
expenditure-side cross-check* of the physical Y (does `Σ p·Y_physical` look
sane against the monetary aggregates?): they have a governed home in nxbase
(parameter `prc`, plus the WB deflators + ECB FX for temporal alignment).

**Mapping caveats:** balances *Residential final consumption* → Y (exclude
own-use / transformation — those are coefficients, not final demand); FBS *Food*
→ Y (net of losses/processing; FAO ↔ EXIOBASE commodity concordance).
