# Transport service layer — design plan (built *before* the first nowcast)

> Part of the **nxsut update master plan** — see [nxsut_update_plan.md](nxsut_update_plan.md) for the pipeline order, status and build sequence.

Companion to [tech_coefficient_update_plan.md](tech_coefficient_update_plan.md)
and [nowcast_lp_cvxlab_draft.md](nowcast_lp_cvxlab_draft.md). Decided with
Lorenzo on 2026-08-01: the transport restructuring is **conceptually upstream**
of the nowcast (it is a prior transformation, like the supply/trade-mix updates
and the autoproduction netting), and since there is no deadline pressure it is
built **first** — so the first production nowcast already constrains the UNSD
balances against the *right* transport structure, and the fallback bucket
treatment (LP draft D11) is never exercised.

## Why (the root problem this solves)

Energy and economic accounting are structurally incoherent on transport.
Energy statistics classify fuel by **mode** (`1221` road = hauliers + every
sector's own-account logistics + households' private cars; `1231` residential
*excludes* transport). The economic table classifies by **user** (H.49 buys
only the hauliers' fuel; own-account fuel sits in each industry; household
fuel is final demand). Any split of the balance flows onto the economic
structure is a *repartition*, not a model. The root fix is **activity-based
bottom-up**: fuel follows the observed activity of vehicles, not the purchase
statistics — and the mismatch dissolves by construction. It also delivers the
transition-critical sectors Nicolò asked for (private transport, freight) as
first-class objects.

## Architecture — the electricity pattern applied to transport

Three stacked scenario levers, mirroring power:

1. **Inter-modal needs** (the top): a modal-agnostic **`Mobility` need in
   pkm** (households; optionally a business-travel slice) and a **`Freight`
   need in tkm** (sectors). The nxbase `need` level was designed for exactly
   this (*mobility* is a canonical need example in the KB) and the **`mkt`**
   parameter is the market-share grammar: **modal shift** (car→rail,
   road→rail freight) becomes a share update, like the electricity supply
   mix.
2. **Vehicle technologies within each mode** (the middle): car
   gasoline/diesel/BEV, motorcycle, bus diesel/electric, rail
   electric/diesel, LCV/HGV classes, rail freight, inland waterway, domestic
   maritime, domestic aviation. In nxbase these are `technology` rows — the
   technology tree's canonical example *is* vehicles (`Model 3 → BEV →
   Vehicle`) — paired with per-region activities in the table
   (`adopted_technology` link, the Ghezzi-route precedent). MIMO's cvxlab
   model is the in-family template (`light_transport_hh` /
   `light_transport_serv` / `heavy_transport`, activity in `MVkm` /
   `MVkm-ton`, stocks as capacity).
3. **Recipes** (the bottom): the *simplest technology inventories that
   exist* — `fuel economy (MJ/vkm) × occupancy (pkm/vkm)` for passenger,
   `× load (tkm/vkm)` for freight; BEV and electric rail take electricity
   as input (linking transport electrification to the power block). Fuel
   use reconstructs bottom-up as `Σ tech vkm × economy`.

**New units**: `vkm`, `pkm`, `tkm` (unit rows; the service commodities are
physical, replacing the MEUR-denominated transport services of the base table
for the restructured modes).

## Plumbing into the table (a prior transformation)

`add_sectors`-class operation on the **base-year prior** (before the LP, in
the deterministic pipeline):

1. Extract motor fuels from the user columns (sectors' own-account share,
   households' direct fuel) per the base-year split — the last time the
   2011 repartition is used, as the *initial* condition rather than the
   ongoing model.
2. Create the vehicle-tech activities per region; their fuel input = the
   extracted flows; their output = pkm/tkm service commodities.
3. Deliver services back: pkm to households' `Mobility` need (Y), tkm to
   sectors' intermediate use (in proportion to the extracted own-account
   fuel), pkm/tkm to H.49's market production where applicable.
4. Totals are preserved by construction (fuel moved, not created); the
   operation is BFG/OFG-class, scripted, reversible.

**Nowcast integration** (the payoff): the 2023 observed pkm/tkm/vkm become
**`x_obs` anchors** of the vehicle-tech activities — transport joins
EMBER/worldsteel in the anchor family; the `1221` band becomes *natural*
(the sum of road-tech fuel uses, no Y term, no mask hacks); implied fuel
economies (solved fuel ÷ anchored vkm) become the transport analogue of the
power implied-efficiency radar.

## Disaggregation design — the three moves (agreed with Lorenzo, 2026-08-02)

The "plumbing" above refines into **three distinct moves with different
machinery** — the base table already has commercial transport as sectors
(households already buy bus/rail tickets as services); what is missing is
different in each case:

**Move A — private mobility as MIMO activities** (the structural gap).
Households buy fuels directly in Y; the transport they self-produce is
invisible. Add household-operated `CAR.*` (+`MOTO`) activities producing
the private-mobility service; reroute household fuel purchases from Y into
their use column. The machinery is **FULFILL_MARIO's own add_sectors +
shock template** (it does exactly this); the data is now observed instead
of modelled: vkm per tech = car pkm (ITF/ESTAT) ÷ occupancy (NXTR SUP) ×
car-park share (ESTAT.CARPARK); the declared same-intensity CAR.G/CAR.D
assumption is closed by the LP against observed UNSD 1221 gasoline/diesel
totals.

**Move B — tech/mode split of the existing transport sectors**
(split-in-MEUR-first, then re-denominate — the order dissolves the unit
problem):

1. **Split the parent column in MEUR** (additive, no unit issue) with the
   observed turnover key — governed as **`ESTAT.SBSH49`** in nxbase
   (SBS V12110 × 8 NACE Rev-2 H49 classes; 2,283 rows, 0 skips; IT 2011:
   road freight 70.1% ≡ probe; nxbase `1cc03e2`). Note: EXIOBASE "Other
   land transport" excludes rail (own sector) → the column uses the road+
   pipeline classes, where coverage is strongest (24-27 countries, 2011
   included); rail splits P/F separately (16-21 countries).
2. **Re-denominate each child to its own unit** (HGV → tkm, BUS → pkm,
   TRN.P/F → pkm/tkm): output = the observed Q, coefficients ÷ Q. The
   Merciai move itself — the implicit price M/Q (EUR/tkm ~0.15-0.25,
   EUR/pkm bus ~0.10-0.15) is a *diagnostic output*, never an input.
3. **Carve, don't rebuild**: fuel rows overwritten bottom-up (NXTR × vkm,
   LP-closed vs UNSD 1221); every non-obvious input (tyres, insurance,
   services…) inherited pro-quota — nothing is lost, which is the argument
   against full bottom-up replacement.
4. **Fallback chain for the split key** (measured, 2026-08-02): Eurostat
   SBS (EU/EFTA+candidates) → OECD SDBS (adds KOR, TUR only; **US has no
   turnover there**) → hand-curated big-5 with per-cell provenance (US
   from BEA — its IO already splits truck/transit/rail/pipeline
   *natively*; CN NBS yearbook; JP MLIT) → unit-revenue ratios × ITF
   volumes (only ratios matter) → **observed-median shares as the floor**:
   the MRSUT sector list is uniform across regions, so "no split" is not
   an available tier — RoW aggregates get the declared median structure.
5. **Use-side allocation**: final purchases (households/government) → pkm
   children; intermediate purchases → tkm children; declared
   business-travel exception (service sectors' land-transport purchases →
   pkm: they receive no goods). v1 refinement key: **tonnage received**
   per sector — the hybrid table's mass flows discriminate both sides for
   free.

**Move C — own-account freight**: stays embedded in the user sectors
(30-40% of road tkm per ITF — declared limitation, not an error); HGV
covers hire-and-reward only. Extraction is a v2 candidate.

Order: A+B in one add_sectors pass on the base-year prior, then the LP
nowcasts with mode-level fuel anchors binding to columns that exist.

**(a) Implicit-price diagnostic — RUN (2026-08-02)**
(`transport/moveb_implicit_prices.py` → `moveb_implicit_prices.csv`):
SBS turnover ÷ observed volume per (child, country, Y11+Y19) = implicit
unit revenue, banded. **146 comparisons, 84% in band**, and the Y11
key-country row reads like the textbook: HGV 0.11-0.44 EUR/tkm (PL 0.107
cheap hauliers, IT 0.362 short-haul premium), TRN.P 0.036-0.189 EUR/pkm
(PL cheap, FR TGV premium), BUS ~0.09-0.32, TRN.F 0.01-0.10. The
out-of-band cases are all *explainable* and steer the builder:

- **FR bus = 343 EUR/pkm** → the ESTAT bus-pkm cell is a coverage hole
  (partial vehicle categories); builder rule: per-(child, country) the
  volume source is picked by plausibility (FR bus → ITF), not by a fixed
  preference order;
- **PIPE systematically HIGH** (DE 0.22, IT 0.26 vs band ≤0.10) → the
  H.49.50 turnover covers gas+oil transport, ITF pipeline tkm only part —
  the same perimeter mismatch as the leg-1 pipeline efficiency outliers.
  Consequence: the pipeline child **stays monetary (MEUR)** in v0 — no
  clean Q exists; re-denomination is per-child *where clean*, not dogma;
- **ES rail freight 0.002** → SBS confidentiality/classification hole →
  fallback tier for that cell.

The builder therefore gets two per-cell rules: volume source by
plausibility, and re-denominate only where the implicit price lands in
band (else keep MEUR and flag).

**(b) Non-SBS split master — BUILT (2026-08-02)**
(`transport/build_moveb_split_master.py` → `moveb_split_master.csv`, 65
cells, 13 countries, tier per cell): KOR tier-2 observed (OECD SDBS TUTT
2011, raw slice cached; TUR turned out tier-1 — Eurostat SBS covers
candidates); tier-4 = median in-band implicit price (diagnostic a) ×
ITF volumes — the rails come out with the right character (US 97%
freight, JP 98% pax, CN 60/40, IN 76% pax); tier-5 = SBS-median shares
(bias-fixed: only countries reporting BOTH core children contribute —
confidential rail-pax cells were producing fake zeros; road 80/20, rail
55/45); never a silent zero (missing volumes → median share, declared);
explicit WARNING on PIPE for pipeline-heavy economies (US/CN/RU/CA/KZ);
per-cell upgrade paths (US → BEA native split, CN → NBS, JP → MLIT).

**Split mechanics — DECIDED (2026-08-02, Lorenzo)**: deterministic,
share-based, **no solver at split time, no MARIO changes** (pipeline-side
script on `db.U/S/Y`). A per-cell share split preserves every balance
identically by construction; optimization belongs to ONE layer only —
the nowcast LP, where child anchors (pkm/tkm, mode fuel bands) reconcile
priors vs observations. The CE prototype (ENTICE, monetary SUT) is the
template for over-determined base-year splits (GTAP-style) and trade
re-splits; its SUT-hybrid port = the relative-weights fix (same as the
toy LP) — queued, off the critical path. Per-row-class keys: liquid-fuel
rows → bottom-up shares (NXTR intensity × vkm from Q/yield), all other
inputs + VA → SBS tier-chain shares (electricity/gas rows included, v0
declared — minor rows); supply → SBS shares then re-denominate (BUS →
pkm, HGV → tkm, PIPE stays MEUR); use row → final/intermediate rule
(+business-travel exception; pipe use → gas/oil-consuming sectors);
by-product cells → same class keys. Acceptance: re-aggregating the
children reproduces the parent exactly (reversibility test). Use-row
balance note: the final/intermediate rule yields row totals that need not
match the supply split — the apply script closes each parent use row with
a per-row IPF (row targets = supply split × M, column targets = parent
cells): deterministic, tiny, declared.

**Grid discovery (2026-08-02, stage-2 dry-run)**: EXIOBASE hybrid already
carries the NACE-1.1 division-60 split — **"Transport via pipelines" and
"Transport via railways" are separate sectors**; "Other land transport" is
road-only. Consequences: the PIPE child is dropped from Move B (the
existing pipeline sector simply stays MEUR — consistent with the (a)
verdict), the road shares renormalise without it, and the rail P/F split
applies to "Transport via railways". Activity and commodity names differ
("Other land transport" vs "Other land transportation services") — the
apply script keys them separately.

**(c) stage 1 — split spec BUILT (2026-08-02)**
(`transport/build_moveb_split_spec.py` → `moveb_split_spec.csv`): 686
rows, **all 49 EXIOBASE regions covered**, per (region, block, row_class,
child) with tier + provenance. Monetary key tiers: road_pipe = 22
SBS-observed + 1 SDBS + 7 price×volume + 19 median; rail = 13 + 8 + 28.
Fuel rows carry the bottom-up shares (vkm × NXTR intensity, per-country
observed load factors where available); Q rows carry the re-denomination
targets (missing Q → child stays MEUR, declared). Spot: IT fully
observed (road 77/18/4, rail 94/6 pax — the Italian structure), US/CN
tier-4 with the right rail characters (US 97% freight, CN 60/40), RoW on
the median.

**(c) stage 2a — dry-run on the real table PASSED (2026-08-02)**
(`transport/apply_moveb_split.py` → `moveb_split_dryrun.csv`, MARIO env,
db never mutated): 48 regions × 2 blocks, **reversibility 7.5e-09** (float
eps) on every column/cell, IPF row residual 2.2e-05. Numbers: IT road
86.5/20.6 b€ (81/19), rail 12.2/0.8 (94/6); DE road 66/34 (the ÖPNV
weight, observed SBS); US rail 97% freight / CN 60-40 as designed. Two
mechanics lessons banked: (i) negative user cells (inventory changes)
split by supply shares OUTSIDE the IPF (mixed signs break scaling);
(ii) IPF seed = 90% rule + 10% proportional (the declared business-travel
allowance — also removes unreachable zero rows). pandas-3 CoW: to_numpy
needs explicit copies. **Finding**: table-implied prices (IT FRT 0.67
EUR/tkm) ≈ 2× the SBS-implied (0.36) — the use row embeds margin-type
flows and basic-vs-purchasers price differences; harmless for the split
(shares), essential context when comparing children to observed revenues.
**Move A — private mobility WRITTEN into the table (2026-08-02)**
(`transport/build_movea_spec.py` + `transport/apply_movea_write.py` →
export `out/_transport_table`, the A+B combined baseline; spec and diag
committed under `transport/data/`): six household-operated activities
(CAR.G/D/LPG/CNG/E + MOTO) supplying one "Private road mobility"
commodity (Mpkm), household motor fuels rerouted from Y (per-carrier
caps, origin structure pro-rata, EY untouched, VA=0). Checks: exact fuel
conservation; world private pkm 16.03M Mpkm (G/D 79/19, CAR.E 3.5 Gpkm
in 2011 — right order); **IT 566,746 Mpkm with gasoline coverage 1.0** —
the cap vs household purchases lands at 85% of observed total car pkm,
i.e. the company-car share (fuel booked in sectors) emerges from the
data. 24/48 regions gasoline-anchor synthesised (declared). Three bugs
caught by the checks across v3-v5: Mvkm-vs-vkm unit scale on fuel
demand; the NPISH column matching "households"; and **multi-supplier s
must carry supply SHARES** (a flat 1 hands every tech the full regional
commodity output — Xa = s·Xc); plus a spec-side coverage hole (ES/GR
carpark Y13 report only the ELC row → silent 100% electric — the
core-valid-year rule now guards it, same doctrine as the SBS medians).

**FIRST INTEGRATED VINTAGE — v3.2 / 2023 BUILT (2026-08-02)**: full
gen_v3 run, headless, exit 0 → `nxsut/v3.2/2023/flows` (1.0 GB). Grid
48 × **201 activity** × 205 commodity; the pipeline ran transport (B: IT
road freight 127,802 Mtkm; A: IT 566,746 Mpkm at gasoline coverage 1.0;
C), then the **UNSD-first supply mix** (`blended supply mix — 172
(country, year) from UNSD.GEN, 27 from EMBER` — the blend really engages
for 2023), steel routes, pooling and the BACI/ENTSO-E trade mixes.
Acceptance (`transport/validate_v32.py`): all eleven transport
activities present, 3 pooled commodities, 11 route/steel activities.

Footprints (GHG AR6, g/unit) read exactly as physics predicts:

| | IT | DE | PL |
|---|---|---|---|
| private car gasoline / diesel | 126 / 130 | 151 / 155 | 131 / 135 |
| private car CNG / electric | 70 / **49** | 70 / **55** | 71 / 0 |
| road freight (hire) | 100 | 35 | 16 |
| rail passenger / freight | 63 / 13 | 72 / 36 | 53 / 59 |
| own-account road freight | 119 | 119 | 119 |
| **electricity need** | **334 g/kWh** | 361 | 688 (FR 86) |

Two things worth noting. **The BEV now costs 49 g/pkm instead of the 88
of the 2011-mix table** — the arithmetic closes on the updated grid
(0.22 kWh/km ÷ 1.5 occupancy × 334 gCO2/kWh ≈ 49), i.e. the supply-mix
update propagates into the transport layer exactly as intended; and the
electricity anchors are **2023 values** (IT 334, FR 86 nuclear, PL 688
coal, DE 361), not the 2011 base — the strongest evidence that the
UNSD-first mixes landed. **Own-account is identical across countries
(119)** because its v0 recipe is country-invariant (default load factor
7.2 tkm/vkm everywhere, single diesel intensity): a declared v1
refinement — wire the per-country observed own load factors where leg-1
has them.

**Move B extended to water and air (2026-08-02, Lorenzo: "proviamoci,
anche a costo di accorpare inland e sea coastal")**: three more parents
split passenger/freight — sea and coastal water, inland water, air. No
merge was needed: ITF publishes coastal and inland-waterway tkm
separately. Governed inputs added in nxbase: the **SBS slice extended to
H50/H51** (1:1 with the NACE 2.1 classes, so still zero source-specific
set rows; 3,838 rows) and **WB.AIRFRT** (World Bank IS.AIR.GOOD.MT.K1,
ICAO-derived carrier tonne-km, 3,342 rows keyed onto NACE H.51.21).

The re-denomination rule stays the declared one — physical only where a
clean Q exists:

| child | denomination | Q source |
|---|---|---|
| sea / inland freight | Mtkm | ITF coastal, ITF inland waterways |
| air freight | Mtkm | World Bank (ICAO) |
| sea / inland / air passenger | **MEUR** | none open (only passengers carried) |

Observed monetary split (IT 2011): sea 54/46 freight-passenger, inland
waterways 27/73 (Italy's are mostly passenger — lakes and the lagoon),
air 1.3/98.7 (the dedicated air-cargo sector is tiny because belly cargo
sits inside the passenger airlines' revenue). Observed-tier coverage:
sea 16 countries, inland 13, air 15; the rest fall to the median tier.
Perimeter caveat carried into the source notes: the WB air indicator is
carrier-based including international legs and the EXIOBASE sea sector
includes international shipping, while the ITF modes are
territory-based — the implicit-price diagnostic tests each child before
re-denominating, and a child that lands out of band stays monetary.

**Pipeline integration (2026-08-02)**: the three moves are refactored from
standalone scripts into `apply(db)` functions and chained by
`transport/pipeline.py` → `apply_transport_layer(db)`, applied **in
memory** (the dev scripts keep their `main()` for isolated runs with the
900 MB exports; the pipeline no longer pays them). gen_v3 gains one cell
after the furnace-gas block and before the mix updates — so the BEV
activity's electricity input joins the electricity pooling downstream —
plus the supply-mix swap `get_ember_snapshot` →
`get_supply_mix_snapshot(years=(year,))` (the step-0 arbitrated blend;
degrades to pure EMBER for years UNSD does not cover). `calc_ghg` is
skipped inside the moves (`validate=False`) and belongs downstream, after
every move has landed.

**Move C — own-account road freight WRITTEN (2026-08-02, decided with
Lorenzo: before the nowcast)** (`transport/build_movec_spec.py` +
`apply_movec_write.py`, commit `c85d1b8`; export refreshed): the sectors'
internal logistics externalised as one activity per region producing a
separate "Own-account road transport" commodity (Mtkm) each sector buys
back — the SNA ancillary externalisation, data-driven. Governed key:
**observed NST2007 own-account propensities** (nxbase ESTAT.ROADGOODS,
`8671c55`: removals 44%, waste 28%, construction minerals 19%, agri-food
~18%, metals 9.6%, chemicals 8.4%; own = 15.4% of EU tkm). Allocation =
column diesel × declared propensity (off-road-dampened), class caps
(fleet cells 0.8, others 0.5), waterfall; **realism-tuned over three
dry-runs**: heavy/process industry excluded from the pool (PL "Chemicals
nec" holds 2.4 Mt of feedstock-grade diesel and dominated at any small
weight — never fleet fuel), un-hostable residual stays embedded and
reported (**PL and GB gap 9%** — the honest reading of thin EXIOBASE
columns, Lorenzo's predicted case). IT/DE textbook (wholesale/retail/
construction/food top, gentle cell shares). Direct CO2 moves with the
fuel (IPCC diesel EF, satellite-capped); fuel-only, VA stays. **World
own-account X = 2.17M Mtkm = 13.9% of total road tkm vs 15.4% observed
EU** — the aggregate closes on the statistics. UNSD alignment achieved:
1221 = transport-family columns; industry rows keep process/heating/
off-road. Hygiene note: the dev export's 'GHG AR6' satellite row is
stale (pre-C); CO2/CH4/N2O rows are the truth — the gen_v3 integration
runs calc_ghg after all moves.

**Footprint validation + EY→E reattribution (2026-08-02, after Lorenzo's
f-check)**: the first `calc_ghg` on the combined table showed private cars
at 25-45 g/pkm — the declared EY-untouched v0 left the tailpipe in the
household satellite. Fixed in the apply (commit `fd6e1ec`): household
driving combustion re-attributed EY→E with declared IPCC CO2 EFs
(3.07/3.17/3.02/2.75 t/t; CO2-only v0), per-region caps, **conservation
exact (error 0.0, no EY shortfalls)**. Validated in-run: CAR.G 127-152
g/pkm, CAR.D 131-156 (≈190-235 g/vkm — the expected ~200), direct = fuel
× EF to the gram; CAR.E honestly comparable at 88 g/pkm on 2011 mixes
(PL 0 = zero BEV fleet). **The same table quantifies Lorenzo's
own-account intuition**: the commercial children's DIRECT emissions span
an order of magnitude (road freight IT 33 g/tkm vs PL 1.5; bus IT 21 vs
PL 0.9) — the in-sector share of trucking fuel/emissions varies by
country, the rest is own-account embedded in user sectors (Move C).
Consequence: per-tkm footprints of the B children are NOT cross-country
comparable until the own-account extraction (v1); the nowcast anchors
(UNSD 1221 spans sectors) are unaffected. TRN.P totals (63-101 g/pkm,
direct ~0 where electric) include the full inherited monetary upstream —
in band with full-LCA rail figures, to keep an eye on. Parent folding
via aggregate: blocked by the MEUR-vs-Mtkm unit check (cosmetic;
activities-only fold possible at integration time).

**(c) stage 2b — split WRITTEN into the table (2026-08-02)**
(`transport/apply_moveb_split_write.py` → export
`transport/_moveb_split_table/flows`, 897 MB): children registered via
the standard `read_add_sectors_excel` + `add_sectors()` path
(register-only template generated from the blastfurnacegas base — NOT
the `split=True`/cvxlab path, which exists in the signature but is
IOT-only); surgery in two phases (compute into dicts, then bulk writes:
columns on the natural axis, rows via one transpose round-trip per
matrix — repeated `.loc` row writes on the 70M-cell frames consolidate
the whole block per call under pandas-3 CoW and ran for hours before the
rewrite); `update_scenarios('baseline', z, v, e, Y)` +
`reset_to_coefficients`. **Checks**: parents exactly 0; IT ROAD.FRT
X = 127,800 vs observed Q 129,084 Mtkm (99% — the ~1% is the self-use
fixed point at rebuild, prior-grade); world TRN.P 3,293 Gpkm (real
~2,900 ✓), ROAD.FRT 13,463 Gtkm; 61/192 child outputs synthesised
(M ÷ median table price — RoW and US/CN buses, declared). Two real bugs
caught by the X-vs-Q check: (i) the physical scale divided by total M
instead of the child's M; (ii) **transport self-use** (subcontracting,
~30% of road freight!) landed on dead parent cells and vanished —
now an explicit child→child diagonal block (freight subcontracts
freight; coeff = self_val/M). Next: plug the split step into gen_v3
(after aggregate_ee, before supply-mix updates) and Move A on top.

## Data map (endpoints verified with live calls, 2026-08-01)

| block | source | verified detail |
|---|---|---|
| pkm/tkm EU | **Eurostat** (open API, JSON/SDMX) | `road_pa_mov` (pkm by vehicle type, IT series 1970-2024), `rail_pa_total`, `tran_hv_psmod`/`frmod` (modal split), **`road_go_ta_tott`** — tkm **by type of operation: own-account vs hire & reward** (the freight own-account split is *observed* in the EU) |
| pkm/tkm world | **ITF/OECD** (SDMX `sdmx.oecd.org`, agency `OECD.ITF`, CSV, open w/ attribution) | `DSD_TRENDS@DF_TRENDSPASS` / `DF_TRENDSFREIGHT`: **48 countries incl. CN, US, JP, KR, CA, AU, MX, TR**, by mode, to 2023 (live-fetched sample: IT rail 2023 = 54 791 Mpkm) |
| vkm / fuel cross-checks | ITF `DSD_ST@DF_STTRAFFIC` (road vehicle-km), `DF_STFUEL` (motor fuel deliveries — reconciliation cross-check), `DF_STREG` (new registrations) | listed on the same API |
| fuel economy | **EEA CO2 monitoring** (EU new registrations, fully open, per-vehicle); **GFEI benchmarking** (by country, latest 2019-2022) + **ICCT** market stats (report-grade) | licensing of GFEI/ICCT redistribution to verify |
| stocks | **OICA** vehicles-in-use (free) | proxy backbone for no-survey countries |
| validation | **UNFCCC CRF `1.A.3.b`** (road emissions split cars / light & heavy trucks / buses, Annex-I) | the observed private/commercial split, for validation not construction |
| gaps | India, Brazil, Indonesia, Russia, most of Africa | no open pkm/tkm survey → prior = stock (OICA) × default mileage × GFEI economy; **closed by construction** via the governed UNSD `1221` country band — bottom-up structures the split, the balance closes it. IEA MoMo (the closed gold standard) deliberately avoided. |

## Reconciliation & acceptance tests

1. **Balance bands**: per country, `Σ road-tech fuel ∈ F_obs(1221)·(1±ε)`
   (and `1222/1223/1224` per mode; international aviation/navigation against
   the bunker flows `051/052`, already in the UNSD snapshot).
2. **ITF `STFUEL`** motor-fuel deliveries vs the same totals (independent
   cross-check of UNSD).
3. **CRF `1.A.3.b`** split vs the model's private/freight fuel shares
   (Annex-I).
4. **Implied economies**: reconstructed fuel ÷ observed vkm within GFEI/EEA
   plausibility bands per country.

## Sequencing & deliverables

0. This design doc. ✔
1. **nxbase governance kits** (the UNSD pattern: license verify → pull
   snapshot-first → classification/sets → recipe → import): `ITF` (SDMX
   pull, TRENDSPASS/TRENDSFREIGHT/STTRAFFIC/STFUEL) and `Eurostat
   transport` (the `nrg_bal_c` twin machinery). Licenses to verify
   per-source before the rows exist (OECD terms; Eurostat reuse policy).
2. **Taxonomy + recipe table v0** — **global from day one** (decided
   2026-08-01: no "Italy pilot"; the taxonomy is one, populated where data
   exists, empty where the tech is irrelevant), reviewed before any table
   surgery. See *Taxonomy & recipe schema v0* below.
3. **`add_sectors` template on the prior**; first acceptance check on one
   data-rich region (e.g. IT), then all regions — acceptance = the national
   `1221` balance closes (test 1).
4. Population waves: observed data (EU/OECD+/CN) → proxy countries (stock ×
   mileage × GFEI economy).
5. **First production nowcast** on the transport-restructured prior (LP
   draft D11 retired unused; transport enters via `x_obs` anchors).

## Decisions taken (2026-08-01, Lorenzo — supersede the open questions)

1. **Private car = an activity operated by households** (the MIMO/ESM
   choice, confirmed): fuel and direct emissions move into the car
   activity; households demand pkm. Accounting note to write when the
   table op lands (EXIOBASE household direct emissions relocate; national
   totals unchanged).
2. **Occupancy from Odyssee** (EU stock averages) + declared defaults
   elsewhere; per-country refinement only if the `1221` check does not
   close. Freight load factors are **observed** (road_go tkm/vkm by
   operation).
3. **Tech granularity v0 = 14 techs** (see the taxonomy below): one gas
   (LPG/CNG) car tech — populated where relevant (IT, NL, TR…), empty
   elsewhere; **hybrids folded into gasoline/diesel** as improved fleet
   economies, not separate techs.
4. **Recipes governed in nxbase from day one** (the Ghezzi/GHZ26 pattern):
   vehicle techs in the `technology` tree (under the existing
   `NXB | Vehicle` family; `CAR.E` under the existing `BEV` node), recipe
   values as an assembled inventory source (working name `NXTR.V0`),
   per-cell provenance, `int`-style parameters keyed on `t_<TECH>`.

Still open: electricity rows in the `122x` balance constraints (already
covered: carriers include electricity); business travel (deferred, stays in
service-sector inputs at v0).

## Brick 2b — BUILT (2026-08-01): NXTR.V0 governed in nxbase

Status: the recipe inventory is **assembled and imported** (source
`NXTR.V0`, 1,155 rows, 0 skips: `int` 1,059 + `SUP` 96; commits
nxbase `e0fb7eb` + `71858bf`). Pipeline:

1. `transport/derive_recipes_v0.py` — 1,077 coefficients derived from
   governed data via the query API (rail by carrier = UNSD 1222 ÷ ITF
   pkm+tkm; navigation 1224; pipeline 1226; HGV load factors from the
   road_go vkm snapshot, hire/own split). 3 outliers flagged (FR
   navigation, DE/IT pipeline) → defaults + anomaly register.
2. `transport/extract_fulfill_car.py` — FULFILL_MARIO REF baseline
   (2011/2020/2025, 27 EU countries): per-powertrain intensities
   (origin-summed, native hybrid units; validated vs the known IT 2020
   decode) + market shares (sum to 1 everywhere).
3. `ESTAT.CARPARK` (road_eqs_carpda, snapshot-only source): observed
   powertrain stock shares 2013-2024 (~42 countries) → G/D split and
   the master `mkt` sheet (2,080 rows, **master-only**: the `mkt`
   parameter does not admit Technology tokens yet).
4. `transport/build_nxtr_master.py` → `nxtr_master.xlsx` (sheets:
   data / mkt / excluded / readme), archived in `nxbase_raw/nxtr/`,
   ingested by recipe `nxtr_v0`.

**Divergences from the approved brick-2a table — ARBITRATED (Lorenzo,
2026-08-01: both accepted)**:

- **`CAR.GAS` split into `CAR.LPG` + `CAR.CNG`** — CONFIRMED. Both FULFILL
  and the car-park data observe LPG and methane separately, with different
  carrier commodities (`NXB | LPG` vs `NXB | Natural gas`) and different
  intensities (IT: 47.2 vs 35.4 g/km); the earlier "one gas car tech"
  decision is superseded.
- **`LCV` dropped in v0** — CONFIRMED. No governed activity observation
  (road_go covers >3.5t lorries = HGV; LCV vkm/tkm not observed in
  ITF/Eurostat). Re-enters when a source is found (or as a declared HGV
  sub-share).

**Open design point (next)** — importing the powertrain shares: the honest
native import is the **stock counts** (road_eqs_carpda NR), not the derived
shares (the EMBER rule: absolutes in, mixes derived by the consumer). That
needs a **stock parameter** (e.g. `STK`: item_1 = Technology/Commodity,
attrs Entity;Site;Period, unit = vehicle count) — a tree design decision to
take with Lorenzo, not improvised. Until then the layer reads shares from
the governed snapshot (already works).

## Taxonomy & recipe schema v0 (brick 2a — for review)

**14 technologies**, UPPERCASE shorts (technology = tangible), under
`NXB | Vehicle`:

| short | name | mode / service | carriers | parent |
|---|---|---|---|---|
| `CAR.G` | Passenger car, gasoline | road pkm | gasoline | Vehicle |
| `CAR.D` | Passenger car, diesel | road pkm | diesel | Vehicle |
| `CAR.GAS` | Passenger car, gas (LPG/CNG) | road pkm | LPG/NG | Vehicle |
| `CAR.E` | Passenger car, battery electric | road pkm | electricity | **BEV** (exists) |
| `MOTO` | Motorcycle and moped | road pkm | gasoline | Vehicle |
| `BUS` | Bus and coach | road pkm | diesel (dom.) | Vehicle |
| `TRN.P` | Passenger train | rail pkm | electricity + diesel (observed mix, one tech) | Vehicle |
| `LCV` | Light commercial vehicle | road tkm | diesel/gasoline | Vehicle |
| `HGV` | Heavy goods vehicle | road tkm | diesel | Vehicle |
| `TRN.F` | Freight train | rail tkm | electricity + diesel | Vehicle |
| `BARGE` | Inland waterway vessel | IWW tkm | gas oil | Vehicle |
| `SHIP.DOM` | Domestic/coastal vessel | sea tkm | fuel oil/gas oil | Vehicle |
| `AIR.DOM` | Aircraft, domestic aviation | air pkm | jet kerosene | Vehicle |
| `PIPE.T` | Pipeline transport | pipe tkm | electricity/gas | Vehicle |

**Recipe schema** (three coefficient families per tech, each cell with its
own provenance):

1. **Energy intensity per vkm, by carrier** (`MJ/vkm`; cars natively
   `L/100km` → converted): the technology recipe proper.
2. **Service yield**: occupancy (`pkm/vkm`) or load factor (`tkm/vkm`).
3. Derived at use time: `MJ/pkm = (1)/(2)` — never stored, always derived.

**Population strategy (v0)** — the key economy: for half the techs the
recipe is **derivable from already-governed data**, no new sources needed:

| tech family | economy source | yield source |
|---|---|---|
| cars (G/D/GAS/E) | EEA CO2 monitoring (EU, per country) · GFEI (non-EU) · Odyssee stock averages — *the only block needing new pulls (brick 2b)* | Odyssee occupancy (EU ~1.5-1.7), defaults elsewhere |
| MOTO, BUS | Odyssee / literature defaults | defaults |
| TRN.P / TRN.F | **derived**: UNSD `1222` energy (ele+diesel) ÷ ITF/ESTAT rail pkm+tkm, per country | n/a (intensity directly per pkm/tkm) |
| LCV / HGV | literature defaults (HBEFA/ICCT class averages) | **observed**: road_go `MIO_VKM`/`MIO_TKM` by operation, per country |
| BARGE, SHIP.DOM, AIR.DOM | **derived**: UNSD `1223/1224` + IWW/coastal fuel ÷ ITF activity, per country | n/a |
| PIPE.T | derived: UNSD `1226` ÷ ITF pipeline tkm | n/a |

Proxy countries (no activity survey): stock (OICA) × default mileage ×
GFEI economy, reconciled by the `1221` band — never invented silently.

---

## Upstream: MARIO's zero-output protection reaches live labels (2026-08-03)

Found while chasing table-wide negative outputs in the first all-physical
v3.2 build. **Not patched — MARIO is shared with pv-hlca and ExioSteel, so
it is for Lorenzo to decide.**

`aggregate(..., zero_output_epsilon=1e-30)` protects zero-output items
across an aggregation: it stamps their output with the epsilon so their
coefficients survive the divide. In `_aggregate_sut_split_flows` it then
maps those labels **through the aggregation** and stamps the *resulting*
label as well:

```python
aggregated_preserved_activities = _aggregate_labels(instance, "Xa", preserved_activities, ...)
matrices[scenario]["Xa"].loc[aggregated_preserved_activities, :] = float(zero_output_epsilon)
```

There is no check that the aggregated label is made *only* of zero-output
members. Aggregating an empty item into a non-empty one therefore forces
the **live** sector's output to 1e-30.

What it cost here: the five emptied transport parents were folded into the
transport residual category (63). Sector 63 was zeroed in all 48 regions
while every industry kept buying from it → the table lost its balance and
the Leontief inverse went non-monotone: ~1500 activities with negative
output, `U` down to −5.9e9, and negative GHG footprints for 14 of 17
transport sectors. Two builds shipped with it unnoticed because nothing
gated on the negative-output count.

Suggested upstream fix: restrict the post-aggregation stamp to labels whose
members are **all** zero-output (`preserved ⊇ group`), leaving mixed groups
to the normal `Xa` computed from `S`/`Ya`.

Workaround in the pipeline (`transport/pipeline.py`): the fold target is one
of the emptied parents, so every group is entirely empty and the stamp is
the no-op it is meant to be; plus a pre-check on every group member and a
post-check that no output outside the groups moved.

---

## Stato a fine layer (2026-08-03) — cosa è chiuso e cosa resta

Il layer è costruito, validato e documentato nel readme della v3.2. Qui
resta solo ciò che serve a chi riprende in mano il disegno.

### La regola che ha tenuto insieme il tutto

> Numeratore e denominatore devono descrivere la stessa popolazione. In una
> tavola input-output le emissioni seguono la **residenza** — il carburante
> che l'operatore residente compra, ovunque lo compri — quindi anche il
> lavoro fisico al denominatore dev'essere quello dell'operatore residente,
> ovunque lo svolga.

Non è una regola sul mare: è la regola del layer. L'audit fonte per fonte:
aereo coerente (ICAO/World Bank contano per paese di registrazione del
vettore); strada coerente **e dimostrato** (la dimensione `tra_oper` di
Eurostat `road_go` contiene cabotaggio e cross-trade, cioè lavoro svolto
interamente all'estero, e la ricetta prende il `TOTAL`); ferro quasi
(territoriale, ma i treni si scambiano al confine); **mare e vie interne
no**. Le due che rompono sono esattamente quelle i cui operatori lavorano
abitualmente fuori dal proprio territorio.

### L'acqua porta un figlio solo

Dividere merci da passeggeri richiede entrambi i lati misurati allo stesso
modo, e per l'acqua non è possibile: l'unica osservazione per paese su base
residenza (flotta UNCTAD × lavoro mondiale IMO) è **merci**, e nessuna fonte
aperta pubblica i pkm degli operatori residenti di traghetti e crociere.
Quindi mare e vie interne sono denominati **interi** in tonnellate-km
equivalenti, passeggeri a 100 kg (convenzione ICAO/IATA/EN 16258/GLEC, la
stessa già usata per il carburante aereo).

Costo accettato: il marittimo passeggeri non è più una modalità a sé — ~0,5%
della mobilità passeggeri mondiale, e la parte che non sapevamo misurare in
modo coerente. Residuo dichiarato: il carburante del settore include
traghetti e crociere, il cui lavoro non è al denominatore (~5% del bunker
mondiale, perché un traghetto brucia molto più di una portarinfuse per unità
di lavoro), quindi l'intensità marittima è un limite superiore di quel tanto.

### Se un giorno servisse il marittimo passeggeri

Non è irrecuperabile, ma richiede una fonte che oggi non c'è: pkm dei
traghetti e delle crociere **per paese di residenza dell'operatore**. Le
strade plausibili sono lo split per tipo di nave dello studio IMO
(produttività × intensità × numero navi — modellazione su PDF, non
estrazione) oppure un dato commerciale. Da riaprire solo con un caso d'uso.

### Le vie navigabili interne

Restano territoriali. Le chiatte attraversano i confini — quella olandese
sul Reno tedesco è tkm tedeschi ma carburante olandese — quindi è lo stesso
divario del mare a scala molto minore, senza fonte per chiuderlo. L'Italia è
l'outlier visibile: il suo settore porta la laguna di Venezia contro 144
Mtkm di navigazione padana.

### Fattori di emissione e satellite (2026-08-03)

Due cose fatte a valle del layer e che lo riguardano:

- i **fattori di combustione** non sono più costanti nel codice. Move A e
  Move C li leggono da nxbase (`IPCCGL.EF` × `IPCCGL.NCV`, entrambe tabelle
  IPCC 2006 governate come pubblicate e moltiplicate dal consumer). La
  benzina non cambia — 3,070, quella costante era giusta — mentre diesel,
  GPL e gas naturale erano arrotondati e si spostano dell'1-2%;
- il **satellite è ridotto a un verticale GHG**: 14 conti tenuti, 336
  marcati `unused` in `aggregate_ee.xlsx`. Reversibile con
  `transport/prune_satellite.py --restore`. Conseguenza da ricordare: la
  tavola non può più dimostrare il bilancio di massa di Merciai, e le
  footprint idriche, di suolo e materiali sono fuori per questa vintage.

### Coda del layer, in ordine di valore

1. **quote powertrain oltre l'auto privata** (bus e camion): richiede di
   estendere `mkt` in nxbase ad accettare `Technology`, che oggi non fa;
2. **load factor per paese** dell'own-account, oggi invariante;
3. **CH₄ e N₂O** nella riattribuzione, oggi solo CO₂ (~1-2% del CO₂e
   stradale);
4. **pipeline**: unico settore trasporto ancora monetario, e resta tale
   finché non esiste un tkm che descriva la rete e non una sua parte.
