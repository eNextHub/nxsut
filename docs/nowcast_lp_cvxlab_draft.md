# Nowcast LP on cvxlab — design draft (for review)

> Part of the **nxsut update master plan** — see [nxsut_update_plan.md](nxsut_update_plan.md) for the pipeline order, status and build sequence.

Companion to [tech_coefficient_update_plan.md](tech_coefficient_update_plan.md)
(section *Volumes — final demand*): maps the agreed nowcast/reconciliation model
onto **cvxlab** concretely — sets, data tables/variables, constants, expressions
— as a first draft of the `structure_sets.yml` / `structure_variables.yml` /
`problem.yml` triplet. Drafted 2026-07-31 after a full recon of cvxlab 1.0.1
(readthedocs, installed source, MARIO `split_sectors`, MIMO `model_ESM-SFC-IT`).
**Nothing here is built yet** — this is the reviewable blueprint.

## cvxlab in ten lines (what the recon established)

- A model is a **directory**: settings (3 YAML files or one `model_settings.xlsx`
  with 3 equivalent sheets) + `sets.xlsx` (coordinates) + input data files +
  a generated SQLite `database.db` that holds everything (inputs and results).
- **Sets** are the dimensions. `split_problem: true` sets are *inter-problem*:
  every coordinate combination becomes an independently solved sub-problem
  (scenario grid). Dimension sets index variables (`dim: rows|cols|intra`).
- **Data tables** are SQLite-backed value collections typed
  `exogenous | endogenous | constant | hybrid`; **variables** are named
  *slices* of a table (per-set `dim` + `filters` on set attributes) — one
  table, many symbols (the MARIO/MIMO workhorse pattern).
- **Problems** are lists of string expressions over variable names and a
  restricted operator DSL (`@ tran diag sum mult pow minv shift …`,
  `Minimize/Maximize`, `== <= >=`). No objective ⇒ solved as an equation
  system. Multiple named problems + `hybrid` variables ⇒ block Gauss–Seidel.
- Lifecycle: `create_model_dir` → fill settings → `Model()` → fill `sets.xlsx`
  → `initialize_model_environment()` → fill inputs →
  `refresh_database_and_initialize_problem()` → `run_model()` →
  `load_results_to_database()`. MARIO's `cvxlab_bridge.py` shows how to drive
  every step programmatically (blank-sets → fill → load-coordinates → blank
  data → fill → refresh), which is exactly what our bridge will do.

## Design decisions (proposed)

1. **`regions` × `years` as `split_problem` sets — DECIDED (2026-08-01),
   starting with `years = {2023}`** (UNSD balances reach 2023; 2021-22 join
   later for trend/validation). Per-region grid of **independent small LPs**
   (~4-5k endogenous each), embarrassingly parallel, matching the per-country
   data. Cross-region trade: **fixed import shares** from the trade-mix
   update, and **exports anchored to observed BACI flows** (goods; services
   prior-scaled) — exports are observable, not a frozen prior. **Global
   correctness is audited, not assumed**: post-solve, the world balance per
   commodity (Σ solved exports vs Σ solved imports) must close within
   tolerance — this *is* the global physical-balance check; if violated
   beyond ε, one Gauss-Seidel sweep re-anchors each region's export demand
   from the others' solved imports and re-solves (fast: trade shares are
   fixed). A global coupled solve stays the fallback if the audit keeps
   failing.
2. **Only the energy-carrier rows of U are endogenous.** Dedicated `fuels`
   set = the NXS **energy carriers**: fuels *plus* **electricity** (balances
   `7000` × sector) *plus* **distributed heat** (`8000/8000T` → the existing
   `HWAT` "Steam and hot water supply services" row — present in every NXS
   variant, no disaggregation needed; direct-use geo/solar `DG`/`DS` stay
   out of the constraint). The rest of the technology is frozen as exogenous
   `u0` (Leontief).
3. **L1 objective, deviation measured at endogenous scale — DECIDED
   (2026-08-01), with relative weighting**: `absol(mult(W, U_f − u0_f @
   diag(x)))` — deviation from *prior coefficients times endogenous
   activity* (linear in (U, x), the rigorous "percentage update"), scaled by
   the exogenous weight matrix `W = 1 / max(|prior flow|, floor)`. The
   weighting is what makes the hybrid-unit objective meaningful: it prices a
   **1% adjustment identically** across rows in t, TJ and MEUR and across
   country scales (unweighted L1 would arbitrage units and wipe out small
   entries/countries first). The floor keeps zero-prior cells finite;
   *structural* zeros are enforced by masks (the split_sectors `Zero_mask`
   pattern), never by weights. `absol = cp.abs` via
   `user_defined_operators.py`; problem stays an **LP** → HIGHS/CLARABEL.
   (Alternative kept on the shelf: KL/entropy à la `split_sectors` — conic,
   multiplicative RAS-like adjustments.)
4. **Concordances as exogenous 0/1 incidence tables**, filled by the bridge
   from the nxbase set graph: `B_ires` (activities × IRES buckets — the
   NXS30→IRES walk) and `G_va` (activities × VA groups). Observations bind
   at bucket/group granularity; within-bucket allocation comes from priors.
5. **Identities exact; observations as two-sided bands** `*(1±ε)` (MARIO's
   proven pattern — exact equality on data is numerically brittle).
   Tolerances live in a `scalars` set (MARIO pattern), workbook-editable;
   objective weights live in the `W`/`W_y`/`W_v` data matrices (see the
   validation notes — DCP + hybrid-unit normalization).
6. **Bridge = a script in the nxsut repo** mirroring `mario/ops/cvxlab_bridge.py`:
   chdir into the model dir for every cvxlab call (cvxlab resolves paths
   against CWD), `multiple_input_files=True` + CSV inputs, and the pandas-3
   shims MARIO already carries (cvxlab pins pandas 2.3.3 *because* of the
   settings-pivot bug; MARIO monkeypatches it — reuse that or run in the
   mario env).
7. **Prior = the nxsut table *after* the deterministic updates** (decided
   2026-08-01, from the discussion with Nicolò — not EXIOBASE 2011 re-derived
   inside the LP). Supply mixes (EMBER, routes) and trade mixes
   (BACI/ENTSO-E) are *exact share rewrites from data*: redoing them inside
   the LP would degrade them to estimates. Sequence: deterministic mix
   updates → LP closure with the post-update table as prior; the *same*
   external data re-enters the LP as **elastic anchors**, so "fixed vs free"
   is just the band width ε and consistency is automatic. This also answers
   Nicolò's core concern head-on: the **physical/energy balance is the hard
   skeleton** of the model — balance identities are exact constraints (mass
   conservation per commodity row), and the `F_obs` bands *are* the energy
   balance by construction.
8. **Electricity source hierarchy: UNSD-first, EMBER-as-arbiter — extended
   2026-08-01 (Lorenzo)**. Step 0 selects the source per country: where
   UNSD ≈ EMBER, **UNSD is primary everywhere — use side, `x_obs` anchors
   and the generation mix itself** (it carries the CHP plant-type split
   `015CC/CE/CH`, separated waste-to-energy `01RW/01NRW`, finer by-fuel
   thermal detail incl. `01MG` manufactured gases, and the main/auto split
   the netting needs — all structure-consistent with the Merciai CHP/waste
   by-product activities, which EMBER cannot see); where they diverge or
   UNSD under-reports, EMBER arbitrates. Implied efficiencies (UNSD `088x`
   inputs vs outputs) are the quantitative criterion; EMBER also remains
   the timeliness source (2024+).
9. **Autoproduction netting — a deterministic prior transformation (2026-08-01,
   Lorenzo)**. The prior table has off-diagonal electricity supply (rooftop PV
   on factories, etc.); observed generation cannot attribute it by sector, and
   anchoring `x_power` to *total* generation would double-count it. Fix, applied
   to the prior in gen_v3 (the BFG/OFG pattern), **not** an LP constraint: zero
   the off-diagonal electricity supply of **non-energy activities** and reduce
   the same activities' electricity use by the same amount (self-consumption
   netting), **capped at own use** (no negative U; any excess stays or moves to
   the power activity). Do **not** net the energy-sector by-producers — CHP/heat
   activities (electricity is their structural by-product in the EXIOBASE
   construction) and waste-to-energy (real grid sales, observed by UNSD
   `01RW`/`01NRW`) — for these two, the UNSD plant-type/waste production
   data makes the by-product electricity supply **updatable**, not merely
   exempt from netting. Data leverage: UNSD observes the **main-vs-autoproducer
   split** (`015x` vs `016x` production families, incl. `016SP` solar-PV
   autoproduction; `08811/08812` fuel inputs) — so the netted quota is a datum
   per country/source/year, and the anchor becomes coherent by construction:
   `x_power` ↔ the `015x` main-activity family, with EMBER totals decomposed via
   the UNSD split (a step-0 task). Reversible: grid sales by non-energy sectors
   can return later as an explicit autoproducer activity (add_sectors pattern).
10. **Power efficiency band — RETIRED AS REDUNDANT (2026-08-01, Lorenzo)**.
    With UNSD-first on *both* sides of the electricity balance, the implied
    efficiency is already confined by construction: the use-side bands
    (`Σ U_f→power ∈ F_obs(088x)·(1±ε_f)`) and the supply-side anchors
    (`x_power ∈ gen_obs(015x)·(1±ε_x)`) imply
    `eff ∈ eff_obs·(1 ± ε_x ± ε_f)` — and the D10 bounds would have been
    computed from the same UNSD balances: the same information entered
    twice (redundant rows at best; an unintended feasible-space cut at
    worst, if the ε calibrations drift apart). Same holds for CHP (heat
    output `8000T` by plant type is observed too). Residual role, **dormant
    guard only**: wide engineering bounds (e.g. thermal 20-65%), activated
    exclusively where the data is one-sided (one balance side masked) *and*
    only if pilots show the slack-absorber pathology — elsewhere the L1
    objective already defends the prior efficiency (`U → u0·x`). Implied
    efficiencies stay alive where they are useful: the step-0 arbitration
    criterion and the post-solve diagnostic radar.
11. **Transport buckets — FALLBACK ONLY (superseded by the v2-first
    decision, 2026-08-01)**: the transport service layer is built *before*
    the first production nowcast (see
    [transport_service_layer_plan.md](transport_service_layer_plan.md)), so
    transport enters the LP through vehicle-tech activities with observed
    vkm/pkm `x_obs` anchors and natural `122x` bands. The treatment below
    is kept documented only as the fallback if the layer stalls.
    Original design (2026-08-01, Lorenzo — the mode-vs-user mismatch). The `122x` balance
    flows are classified by *mode*, not by *user*: `1221` road = transport
    industry + every sector's own-account logistics + **households' private
    cars**; and `1231` residential *excludes* transport. So for the
    transport buckets the band constrains
    `U_f @ B_transport + mult(m_b, Y_f)` — the incidence gains a **Y-side
    term** (households' motor fuel), and `B_transport` columns span *all*
    motor-fuel-using activities (support taken from the prior's fuel-use
    pattern, not from the IRES→NACE graph walk, which stays valid only for
    the Rosetta anchor of the IRES rows). Within-bucket split = prior
    shares (the EXIOBASE hybrid construction already sectorized transport
    fuel; we inherit that 2011 reallocation — the honest v1 limit is that
    no 2023 observation updates it). Household motor-fuel Y anchors come
    from a share of `1221`, never from `1231`. `1223/1224` are domestic
    only; international bunkers are the separate `051/052` flows (in the
    snapshot). Still linear — one extra term in the transport-bucket bands.

## Draft `structure_sets.yml`

```yaml
regions:
    description: NXS/EXIOBASE regions (49)
    split_problem: true
years:
    description: target years (2021-2023)
    split_problem: true
activities:
    description: NXS30 activities (~190)
    filters:
        anchored: [ember, wsteel]        # output-anchored subsets
commodities:
    description: NXS products (~200)
    filters:
        role: [fuel, nonfuel]
fuels:
    description: fuel commodities (ordered copy of commodities role=fuel)
buckets:
    description: IRES consuming-sector buckets (balance granularity)
va_groups:
    description: aggregated value-added target groups (~15)
scalars:
    description: tolerances and objective weights
    filters:
        kind: [tolerance, weight]
```

## Draft `structure_variables.yml` (core tables)

```yaml
# ---- endogenous ----
x:
    description: activity output, target year
    type: endogenous
    coordinates: [regions, years, activities]
    variables_info:
        x: {nonneg: true, activities: {dim: rows}}
U_fuel:
    description: fuel-use flows (the free technology rows)
    type: endogenous
    coordinates: [regions, years, fuels, activities]
    variables_info:
        U_f: {nonneg: true, fuels: {dim: rows}, activities: {dim: cols}}
Y:
    description: final demand by product
    type: endogenous
    coordinates: [regions, years, commodities]
    variables_info:
        Y_f:  {nonneg: true, commodities: {dim: rows, filters: {role: [fuel]}}}
        Y_nf: {nonneg: true, commodities: {dim: rows, filters: {role: [nonfuel]}}}
V:
    description: value added by activity
    type: endogenous
    coordinates: [regions, years, activities]
    variables_info:
        V: {activities: {dim: rows}}
IM:
    description: imports by product (aux, trade-share closure)
    type: endogenous
    coordinates: [regions, years, commodities]
    variables_info:
        IM_f:  {nonneg: true, commodities: {dim: rows, filters: {role: [fuel]}}}
        IM_nf: {nonneg: true, commodities: {dim: rows, filters: {role: [nonfuel]}}}

# ---- exogenous: priors (shared across years — no years coordinate) ----
s_prior:        # supply coefficients, post supply-mix update (EMBER, routes)
    type: exogenous
    coordinates: [regions, commodities, activities]
    variables_info:
        s_f:  {commodities: {dim: rows, filters: {role: [fuel]}}, activities: {dim: cols}}
        s_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}, activities: {dim: cols}}
u0_nonfuel:     # frozen technology
    type: exogenous
    coordinates: [regions, commodities, activities]
    variables_info:
        u0_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}, activities: {dim: cols}}
u0_fuel:        # prior fuel coefficients (the L1 anchor)
    type: exogenous
    coordinates: [regions, fuels, activities]
    variables_info:
        u0_f: {fuels: {dim: rows}, activities: {dim: cols}}
v0:             # prior VA coefficients (per unit activity output)
    type: exogenous
    coordinates: [regions, activities]
    variables_info:
        v0: {activities: {dim: rows}}
im_sh:          # import shares from the trade-mix update (BACI / ENTSO-E)
    type: exogenous
    coordinates: [regions, commodities]
    variables_info:
        im_sh_f:  {commodities: {dim: rows, filters: {role: [fuel]}}}
        im_sh_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}}

# ---- exogenous: observations (per year) ----
F_obs:          # energy-balance fuel use per IRES bucket (UNSD.USE / Eurostat)
    type: exogenous
    coordinates: [regions, years, fuels, buckets]
    variables_info:
        F_obs: {fuels: {dim: rows}, buckets: {dim: cols}, blank_fill: 0}
M_fuel:         # 0/1 observation mask of F_obs — its OWN table (validation
                # lesson 1): bands bind only where the country reports that
                # (fuel x bucket); "not reported" must never read as
                # "observed zero". Coarse reporters bind on the 121 aggregate
                # only (no double counting: 121 = sum of its sub-buckets).
    type: exogenous
    coordinates: [regions, years, fuels, buckets]
    variables_info:
        M_f: {fuels: {dim: rows}, buckets: {dim: cols}, blank_fill: 0}
W_fuel:         # relative L1 weights = 1/max(|prior flow|, floor)
    type: exogenous
    coordinates: [regions, fuels, activities]
    variables_info:
        W: {fuels: {dim: rows}, activities: {dim: cols}}
W_y:            # idem for final demand (per-commodity prior scale)
    type: exogenous
    coordinates: [regions, commodities]
    variables_info:
        Wy_f:  {commodities: {dim: rows, filters: {role: [fuel]}}}
        Wy_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}}
W_v:            # idem for value added
    type: exogenous
    coordinates: [regions, activities]
    variables_info:
        Wv: {activities: {dim: rows}}
x_obs:          # output anchors (EMBER TWh by power tech; worldsteel)
    type: exogenous
    coordinates: [regions, years, activities]
    variables_info:
        x_obs: {activities: {dim: rows}, blank_fill: 0}
m_x:            # 0/1 mask of anchored activities
    type: exogenous
    coordinates: [regions, years, activities]
    variables_info:
        m_x: {activities: {dim: rows}, blank_fill: 0}
Y_obs:          # Y anchors (residential fuels 1231; FAOSTAT food)
    type: exogenous
    coordinates: [regions, years, commodities]
    variables_info:
        Y_obs_f: {commodities: {dim: rows, filters: {role: [fuel]}}, blank_fill: 0}
        # (nonfuel slices analogous, for food)
M_y:            # 0/1 observation mask of Y_obs — separate table (lesson 1)
    type: exogenous
    coordinates: [regions, years, commodities]
    variables_info:
        m_y_f: {commodities: {dim: rows, filters: {role: [fuel]}}, blank_fill: 0}
Y_prior:        # nowcast prior for the free Y components
    type: exogenous
    coordinates: [regions, years, commodities]
    variables_info:
        Y0_f:  {commodities: {dim: rows, filters: {role: [fuel]}}}
        Y0_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}}
EXP:            # exports — OBSERVED from BACI for goods (per origin x year),
                # prior-scaled for services; not a frozen 2011 prior
    type: exogenous
    coordinates: [regions, years, commodities]
    variables_info:
        EXP_f:  {commodities: {dim: rows, filters: {role: [fuel]}}}
        EXP_nf: {commodities: {dim: rows, filters: {role: [nonfuel]}}}
VA_tgt:         # EXIOBASE 3.10.2 VA (to 2024), aggregated groups
    type: exogenous
    coordinates: [regions, years, va_groups]
    variables_info:
        VA_tgt: {va_groups: {dim: rows}}
GDP:
    type: exogenous
    coordinates: [regions, years]
    variables_info:
        GDP: {}          # scalar per (region, year) sub-problem

# ---- exogenous: concordances (0/1, bridge-generated from the nxbase graph) ----
B_ires:
    type: exogenous
    coordinates: [activities, buckets]
    variables_info:
        B: {activities: {dim: rows}, buckets: {dim: cols}}
G_va:
    type: exogenous
    coordinates: [activities, va_groups]
    variables_info:
        G: {activities: {dim: rows}, va_groups: {dim: cols}}

# ---- scalars (weights/tolerances) & constants ----
tol:
    type: exogenous
    coordinates: [scalars]
    variables_info:
        eps_f: {scalars: {filters: {kind: [tolerance]}}}   # one row each:
        eps_x: {scalars: {filters: {kind: [tolerance]}}}   # eps_f eps_x eps_y eps_g
        eps_y: {scalars: {filters: {kind: [tolerance]}}}
        eps_g: {scalars: {filters: {kind: [tolerance]}}}
        # objective weights live in the W/W_y/W_v matrices (DCP + unit
        # normalization), not here
i_a:
    description: activity sum vector
    type: constant
    coordinates: [activities]
    variables_info:
        i_a: {value: sum_vector, activities: {dim: rows}}
```

## Draft `problem.yml`

```yaml
objective:
    - >-
      Minimize( w_u * sum(absol(U_f - u0_f @ diag(x)))
              + w_y * ( sum(absol(Y_f - Y0_f)) + sum(absol(Y_nf - Y0_nf)) )
              + w_v * sum(absol(V - mult(v0, x))) )
expressions:
    # ---- accounting identities (EXACT) ----
    - 's_f  @ x + IM_f  == U_f @ i_a + Y_f  + EXP_f'     # fuel commodity balance
    - 's_nf @ x + IM_nf == u0_nf @ x + Y_nf + EXP_nf'    # non-fuel balance (frozen tech)
    - 'IM_f  == mult(im_sh_f,  U_f @ i_a + Y_f)'         # trade-share closure
    - 'IM_nf == mult(im_sh_nf, u0_nf @ x + Y_nf)'
    # ---- observations (ELASTIC, two-sided bands) ----
    - 'U_f @ B <= mult(F_obs, 1 + eps_f)'                # energy balances per bucket
    - 'U_f @ B >= mult(F_obs, 1 - eps_f)'
    - 'mult(m_x, x) <= mult(m_x, x_obs) * (1 + eps_x)'   # EMBER / worldsteel output anchors
    - 'mult(m_x, x) >= mult(m_x, x_obs) * (1 - eps_x)'
    - 'mult(m_y_f, Y_f) <= mult(m_y_f, Y_obs_f) * (1 + eps_y)'   # residential energy (+ food twin)
    - 'mult(m_y_f, Y_f) >= mult(m_y_f, Y_obs_f) * (1 - eps_y)'
    - 'tran(G) @ V <= mult(VA_tgt, 1 + eps_g)'           # VA targets, aggregated groups
    - 'tran(G) @ V >= mult(VA_tgt, 1 - eps_g)'
    - 'sum(V) <= GDP * (1 + eps_g)'                      # GDP closure (per country)
    - 'sum(V) >= GDP * (1 - eps_g)'
```

`user_defined_operators.py` (gotcha: import modules only — every module-level
callable gets registered):

```python
import cvxpy as cp

def absol(expression):
    return cp.abs(expression)
```

## Where each exogenous number comes from

| table | source |
|---|---|
| `F_obs` | **UNSD.USE** (nxbase, 2021-23, open) + Eurostat `nrg_bal_c` for EU |
| `x_obs` | **EMBER** generation (nxbase, `OUT`) · **worldsteel** (WSTEEL) — power anchors arbitrated vs UNSD per step 0 (D8) |
| `Y_obs` | balances flow `1231` households (the `CON` sibling recipe) · FAOSTAT FBS |
| `VA_tgt`, `GDP` | **EXIOBASE 3.10.2** monetary (to 2024; no emissions needed) aggregated; WB deflators + ECB FX (nxbase) for constant-price alignment |
| `s_prior`, `u0_*`, `v0`, `Y_prior` | current nxsut table (post supply-mix + trade update) via MARIO |
| `EXP` | **BACI observed exports** (goods, per origin × year — the full local table); services prior-scaled |
| `im_sh` | trade-mix update output (BACI / ENTSO-E) |
| `B_ires`, `G_va` | **nxbase set graph** (NXS30→NACE→bridge→IRES walk; VA groups) |
| inventory-change Y anchors | **UNSD flow `06` Stock changes** (per fuel × country × year — already in the governed snapshot, all transactions were pulled) · FAO FBS *Stock Variation* (food) · EXIOBASE 3.10.2 monetary inventory column as prior for the rest |
| candidate extra `x_obs` anchors (later) | **UNSD Industrial Commodity Statistics** (same UNdata SDMX family — physical production of ~600 industrial commodities) · **USGS** mineral/metal production (public domain) · **FAOSTAT** production (agri) · capacity sanity bounds (EMBER capacity: `x_power ≤ cap·8760·CF_max`) |
| electricity prices (expenditure-side cross-check) | **GTAP** price file (the eNextGen electricity-footprint article dataset) — governable as a `visibility=local` source (GTAP licence is proprietary, never hosted); `scripts/gtap/` already exists in nxbase |

## Fonti per i vincoli — cosa è reperibile, e cosa vincola davvero (2026-08-03)

La tabella sopra dice da dove viene ogni numero *già previsto*. Questa dice
cosa **si può aggiungere**, in ordine di rapporto valore/sforzo, perché il
punto debole del nowcast non è la LP: è quanti vincoli osservati riusciamo a
metterle sotto. Con pochi vincoli la soluzione è dominata dai prior e il
"nowcast" è un riscalaggio con più passaggi.

**Regola di ammissione**: una fonte entra se è **aperta**, ha una **API o un
bulk stabile** (snapshot-first), e copre **più di una regione**. Le fonti a
un solo paese vanno nel benchmark, non nei vincoli — altrimenti la soluzione
si piega dove il dato c'è.

### Già governate e utilizzabili subito

| fonte | vincola | nota |
|---|---|---|
| `UNSD.USE` | `F_obs` — uso di combustibile per settore | 2021-23, 51.952 righe |
| `UNSD.GEN` · `EMBER.GEN25` | `x_obs` elettrico | arbitrato dallo step 0 |
| `BACI` | `EXP`, `im_sh` | full locale |
| `ITF` · `ESTAT` trasporti | `x_obs` dei figli trasporto | pkm/tkm osservati |
| `WSTEEL` | `x_obs` acciaio | `visibility=local` |
| `IPCCGL.EF` · `IPCCGL.NCV` | non un vincolo: il **ricalcolo** delle emissioni a valle | |

### Da governare, alto valore

1. **UNSD Industrial Commodity Statistics** — produzione fisica di ~600
   commodity industriali per paese e anno, **stessa famiglia SDMX** di
   UNSD Energy, quindi lo script di pull esiste già nella forma giusta. È
   il singolo intervento che aumenta di più il numero di `x_obs`: copre
   cemento, vetro, carta, chimica di base, laterizi, fertilizzanti — cioè
   proprio i settori che oggi non hanno alcuna ancora fisica. **Da fare per
   primo.**
2. **FAOSTAT** — produzione di colture e allevamento, uso del suolo,
   fertilizzanti, foreste; e le **Food Balance Sheets** per il lato domanda
   finale alimentare (`Y_obs`). API pubblica, CC BY 4.0, copertura mondiale
   dal 1961. Il blocco agroalimentare è una fetta grossa delle righe fisiche
   di EXIOBASE e oggi è interamente prior.
3. **World Bank WDI** — PIL, PIL pro capite, popolazione, valore aggiunto per
   macro-settore. Il pattern di pull è **già governato** (`WB.DFL`,
   `WB.AIRFRT`), quindi è mezza giornata. Serve sia come vincolo su `VA_tgt`
   aggregato sia come base del benchmark.
4. **Eurostat `nrg_bal_c`** — gemello UE di UNSD.USE sulla stessa coppia
   IRES/SIEC, qualità superiore e copertura settoriale più fine. CC BY 4.0.
   Sorella naturale di una source già governata.

### Da governare, valore medio

5. **USGS Mineral Commodity Summaries** — produzione mondiale e per paese di
   ~90 minerali e metalli, **pubblico dominio** (governo USA). Chiude i
   settori estrattivi. Formato PDF/Excel, quindi estrazione come per l'IMO.
6. **IAI** (alluminio) e **ICSG** (rame) — le cartelle esistono già
   nell'archivio raw con il solo README, quindi il materiale è stato
   individuato e mai tirato. Licenze da verificare prima di asserire.
7. **UN National Accounts** (UNSD) — PIL per attività ISIC, aperto: dà `VA`
   per settore con più dettaglio del WDI.

### Valutate e scartate come vincolo

- **IEA World Energy Balances** — copertura e qualità migliori di UNSD, ma
  **a pagamento e non redistribuibile**: incompatibile con una catena che
  deve restare riproducibile dall'API aperta.
- **GTAP** — proprietaria; resta candidata come source `visibility=local`
  per il cross-check dei prezzi, mai come vincolo pubblicabile.
- Le fonti nazionali (ISTAT, BEA, NBS…) — preziose ma a un solo paese:
  piegherebbero la soluzione verso chi ha il dato. Vanno nel benchmark.


## Benchmark post-solve — KPI, riferimenti, e cosa possono davvero dire

I vincoli dicono alla LP dove atterrare; il benchmark dice se il posto dove
è atterrata somiglia al mondo. Sono due cose diverse e **non devono usare le
stesse fonti**: un dato usato come vincolo non può poi validare sé stesso.

Forma proposta: uno script sul modello di `transport/validate_v32.py` —
gate strutturale prima, poi KPI contro bande dichiarate, con il *fuori
banda* che è un risultato da leggere e non un errore da nascondere.

### KPI 1 — PIL e PIL pro capite

Riferimento: **World Bank WDI** (aperto). Attenzione a una trappola
metodologica: il valore aggiunto della tavola è a **prezzi base**, il PIL
pubblicato è a **prezzi di mercato**. La differenza sono le imposte al netto
dei contributi sui prodotti, che nella tavola stanno in una riga di fattore
di produzione a sé. Il confronto onesto è quindi o **GVA contro GVA**,
oppure PIL contro somma-VA **più** quella riga. Confrontare direttamente PIL
e somma-VA produce uno scarto sistematico del 10-15% che sembra un errore e
non lo è.

### KPI 2 — emissioni totali per regione e per settore

Riferimento: **EDGAR** (JRC, CC BY 4.0, CO₂/CH₄/N₂O per paese e settore
IPCC, serie lunga). Alternative complementari: **Global Carbon Budget**
(CO₂ fossile per paese), **inventari nazionali UNFCCC** (autorevoli ma solo
Annex I), **Climate TRACE** (aperto, recente, a livello di asset).

Due aggiustamenti obbligatori, e il secondo l'abbiamo appena imparato sul
trasporto marittimo:

- **concordanza settoriale**: EDGAR classifica per settore IPCC, la tavola
  per NACE/NXS. Serve un ponte, e alcune celle non hanno controparte netta
  (i processi industriali IPCC 2 si spalmano su più attività NACE);
- **territorio contro residenza**: EDGAR è **territoriale** e per convenzione
  **esclude i bunker internazionali** dai totali nazionali; la nostra tavola
  è per residenza e li include nel settore armatoriale. Per la Grecia sono
  18,3 Mt di combustibile, cioè la differenza fra i due totali nazionali è
  enorme. Il confronto va fatto o sul **totale mondiale** (dove le due
  convenzioni coincidono) o riportando esplicitamente i bunker.

Il totale mondiale è il primo test da fare, ed è quello che dà il segnale
più pulito: nessuna concordanza, nessuna convenzione di perimetro.

### KPI 3 — intensità carbonica dell'elettricità

Riferimento: **EMBER CO2 intensity**, che è **già governata** in nxbase
(`EMBER.CI25`) e non è usata come vincolo — quindi è un validatore
indipendente pronto all'uso, per paese e per anno, in gCO₂/kWh. È il
benchmark a costo zero e va messo per primo.

### KPI 4 — footprint alimentari

Riferimenti possibili, con caveat di licenza che conta:

- **MATILDA** (matilda.food, Zenodo 10.5281/zenodo.21489158, v1 del
  2026-07-22): database di impatti alimentari per gruppo socio-demografico,
  Leiden/Oxford/WU, con articolo Nature Food 2026. **Licenza CC BY-NC-SA
  4.0**: non commerciale e share-alike. Utilizzabile come **benchmark di
  ricerca**; **non** incorporabile in un prodotto eNextGen né
  ridistribuibile senza share-alike. Se lo usiamo, va governato con una
  licenza nuova (`CCBYNCSA4`, che oggi non c'è nella tabella) e
  `visibility` che rifletta il vincolo NC;
- **BONSAI** — aperto per vocazione, ma è un database IO/LCA completo:
  il confronto è più un *cross-model* che un benchmark contro
  un'osservazione. Utile, diverso;
- **Poore & Nemecek (2018)** — footprint per kg di prodotto alimentare,
  meta-analisi molto citata, formato tabellare semplice. Il riferimento più
  facile per un primo test.

Nota di metodo: le footprint alimentari di letteratura sono quasi sempre
**per kg di prodotto alla porta dell'azienda agricola o al consumo**, mentre
la tavola dà la footprint per unità di output dell'attività. Il confronto
richiede di dichiarare il confine — ed è la stessa classe di problema del
denominatore multi-output già risolta per l'acciaio.

### KPI 5 — intensità energetica

Energia finale per unità di PIL, contro WDI/IEA. Debole come validatore
(dipende da PIL e da energia, entrambi già vincolati), ma utile come segnale
di deriva fra un anno e l'altro.

## Validated end-to-end on cvxlab (2026-08-01)

The full structure was built and **solved** as a toy instance
([`nowcast/toy_model/`](../nowcast/toy_model/): 1 region × 1 year, 3
activities, 4 commodities of which 2 energy carriers, every draft mechanism
exercised — split_problem grid, filtered slices, observation masks, relative
L1 weights, `absol` user operator, elastic bands, HIGHS). Every mechanism
behaved as designed: anchors bind at the nearest band edge (sparse L1
adjustments), the unobserved bucket stays free (mask works), balance
residuals are exactly zero, GDP/VA land inside their bands.

Two **corrections discovered by the validation** (applied to the YAML below):

1. **Masks live in separate tables** (`M_fuel`, `M_x`, `M_y`): two variables
   of one cvxlab table covering the same cells read the *same* data — a
   value and its mask cannot share a table.
2. **All objective weights are data matrices** (`W`, `W_y`, `W_v`), no
   scalar weights in the objective: cvxpy rejects (DCP) a sign-unknown
   Parameter multiplying a convex expression — and the weight matrices were
   needed anyway for hybrid-unit normalization of the Y and V terms, not
   just U. Objective:
   `Minimize( sum(absol(mult(W, U_f - u0_f @ diag(x)))) +
   sum(absol(mult(Wy_f, Y_f - Y0_f))) + sum(absol(mult(Wy_nf, Y_nf -
   Y0_nf))) + sum(absol(mult(Wv, V - mult(v0, x)))) )`.

Operational notes: cvxlab 1.0.1 API is `initialize_model_environment()` →
`refresh_database_and_initialize_problem()` → `run_model()` (the MIMO
notebook's granular calls are the older API); interactive erase prompts need
stdin answers when driving it from scripts; results are read with
`m.variable(name, scenario_key=<n>)`.

## Resolved 2026-08-01 (with Lorenzo)

- **Grid per (region × year)**, starting `{2023}`; global behaviour via the
  world-balance audit + optional Gauss-Seidel sweep (D1).
- **Energy carriers all in**: electricity and distributed heat join the
  endogenous rows; heat maps to the existing `HWAT` row, no disaggregation
  needed (D2).
- **L1 with relative weighting** `W = 1/max(|prior|, floor)` (D3); entropy
  stays the shelf alternative.
- **Observation mask `M_f`** on the balance bands (not-reported ≠ observed
  zero); coarse countries bind on the `121` aggregate only.
- **Inventory changes**: free-signed Y slice, anchored where observable
  (UNSD flow `06` for energy — already in the snapshot; FAO FBS for food),
  EX3.10.2 monetary prior for the rest. Net-tax V rows also free-signed.

## Open points (for review)

1. **Slice ordering contract** — `fuels` set must equal the `role=fuel`
   commodity slice in the same order (bridge-enforced, needs an assert).
2. **Solver** — HIGHS (installed via cvxpy) for LP; MARIO's conic default
   (ECOS/SCS/CLARABEL) only needed if we ever switch to entropy.
3. **Grid validation** — quantify the export-feedback error once: one year,
   grid solve vs one coupled Gauss-Seidel iteration, compare footprints.

*(Resolved 2026-08-01: the heat-node duplication is fixed — SIEC
`8000/8000T/DG/DS` anchor to the pre-existing `NXB | Steam and hot water`,
the stale `HEAT` node is removed, and the 4 `HWAT` variant rows re-anchored
there from EBOPS 10.3.5 — the SIEC↔NXS heat concordance is now a shared
parent in the graph.)*

## Review 2026-08-03 — the draft against the built v3.2 (D12–D18)

The draft above was written before the v3.2 vintage existed. Now that the
table is built (transport service layer + UNSD-first mixes, year 2023), the
design was re-read against the real grid. Everything structural survives —
the LP shape, the identities, the elastic-band machinery, the priors-after-
deterministic-updates sequence. What changes is concrete: the sets, three
constraint families, and the data build order. Numbered as decisions D12–D18.

**D12 — Grid constants come from the built table.** 48 regions (not 49 —
hybrid EXIOBASE has 43 countries + 5 RoW), **201 activities × 205
commodities**. The `fuels` set is now enumerable from `units.txt`: the
**~55 SIEC-mappable energy-carrier rows** — the fuel commodities in tonnes
(coals, cokes, manufactured gases, oil products, biofuels, natural gas,
peat) plus `Electricity` **and `Electricity need`** (TJ, see D13) and
`Steam and hot water supply services` (TJ, the `HWAT` row). **`Nuclear
fuel` stays exogenous**: no energy-balance observation prices its use by
sector (UNSD tracks nuclear *heat*, not uranium flows), and the nuclear
activity is already output-anchored via `x_obs`; making the row endogenous
would add freedom with no data to bind it. Feedstock-grade rows (bitumen,
lubricants, paraffin waxes, white spirit, additives) stay **in** the fuels
set but simply have no observation mask anywhere (UNSD non-energy flow `11`
is not imported): the L1 objective keeps them at prior — declared, and the
flow-`11` import remains stage-3 material (carbon balance), not an LP input.

**D13 — The pooled commodities are two rows each; the pool column is
structural.** The trade-pooled commodities (`Electricity`, steel,
aluminium) exist as `X` and `X need` twins: producers supply `X`, one pool
activity per region consumes `X` (domestic + import mix) and supplies
`X need`, consumers buy `X need`. Consequences: (a) both electricity rows
belong to `fuels`; (b) in `B_ires` the **pool activity's column maps to no
bucket** (its use of `Electricity` is plumbing, not sectoral consumption —
counting it would double every kWh against the `7000` balances); (c) the
power-tech columns map to bucket `088` (transformation) through the graph
as-is (NXS power tech → `NXB power*` → NACE D.35.11 → IRES 088 ✓); (d) the
sectoral electricity bands bind on the **`Electricity need` row × consumer
columns**. The supply mixes stay untouchable by construction — `s_prior`
is exogenous, so this falls out for free (the mix update is never redone).

**D14 — Transport constraints, final form.** The service layer changes the
transport blocks from "the hard residual" to the best-observed part of the
model:

- **`x_obs` anchors for the transport children** from the governed volumes
  (ITF/ESTAT pkm-tkm, ICAO/WB air, own-account tkm, private pkm from the
  Move-A machinery), in the activities' own native units (Mpkm/Mtkm). They
  join EMBER/worldsteel in the anchor family, as designed.
- **Road bands regain a Y term — reduced and observed** (the D11 retirement
  was too absolute). Move A moved household motor fuel into the car
  activities *up to the bottom-up cap*; what exceeds the cap stays in
  final demand (France most of all — see `check_fuel_balance.py`). So the
  road balance is: `U_f @ B_road + m_mf·Y_f ∈ (F_obs(1221) +
  F_obs(1231)_mf)·(1±ε)`, where `m_mf` masks the four motor-fuel rows
  (gasoline, gas/diesel oil, LPG, natural gas) and `F_obs(1231)_mf` — the
  households' *stationary* use of those same fuels — moves to the target
  side as an observed constant. Composed with the `1231` anchor on `Y_f`
  itself (the `CON` recipe), the split "stationary vs residual driving"
  is pinned by two observations instead of a declared share. Linear,
  no new machinery.
- **Air and water bands include the bunkers** (residence basis, the layer's
  own rule): air = `1223 + 051` (the carrier-based sector burns ~1.07× the
  domestic+international bunker total), sea = `1224 + 052`. Inland
  waterways stay territorial — declared, as in the layer. Requires
  importing IRES transactions `051/052` (D18).
- Rail = `1222`, pipeline = `1226`, both clean.

**D15 — Autoproduction netting (D9) lands *before* the pilot.** The built
v3.2 does **not** include the netting yet (stage 1c of the master plan).
Since it is a prior transformation and the UNSD `015x/016x` split is
governed, the order is: implement WS-NET in the transport-style
`apply(db)` form, insert it in gen_v3 next to the transport layer, rebuild
the 2023 vintage, and only then bridge the LP. Piloting on the un-netted
table would double-count exactly the autoproduction the anchors are being
decomposed for (rooftop PV is *half* of Italian solar).

**D16 — The v3.2 grid needs its set rows in nxbase.** The `NXS3` namespace
carries the 188 v3.0/3.1 activities: the layer's **15 activities + 10
physical commodities are missing**, so today the `B_ires`/`G_va` walk
cannot see the transport children, and a future v3.2 import could not
resolve its labels. Extension kit (the `enextsut_v3_namespace` pattern):
activities — B-children on their NACE 2.1 classes (road freight → H.49.4x,
road passenger → H.49.3, rail P/F → H.49.1/.2, sea → H.50.2, inland →
H.50.4, air P/F → H.51.1/.21), private car/moto on `NXB | Private road
mobility`, own-account on the ITF own-account row (containment, the one
honest parent); commodities — the service rows on their EBOPS transport
leaves (or `MOB.PASS`/`MOB.FRT` where EBOPS has no mode split at that
grain). With those rows in place `B_ires` is a pure graph walk **plus one
declared rule**: the road-family bucket (`1221`) collects every road
column (B children + own-account + CAR.* + MOTO) — the IRES `122x` rows
anchor at NACE H.49/H.50/H.51 granularity, so the mode-level mapping
inside land transport is the declared piece, mirroring the layer's own
construction.

**D17 — VA targets and the GDP closure.** New **local** source
`EX3102m.VA.*` (EXIOBASE 3.10.2 monetary ixi, reaches 2024): value-added
rows per activity through the existing `VA` parameter (`item_1 = Flow` —
the `VA.*` component flows already exist — `item_2 = Activity`,
`Site;Period`), `from_mario` recipe on the factor-input block. `G_va`
aggregates the 163 EX3m industries onto ~15 groups and the bridge maps
them onto NXS30 activities via the shared EXIOBASE labels (both sides are
EXIOBASE nomenclature — no external concordance). **GDP closure v1 =
Σ VA_tgt from the same source** (self-consistent, no price vector, no
basic-vs-market-prices trap); World Bank WDI GDP is **benchmark only**
(KPI 1, GVA-vs-GVA as the honest comparison). Governing WDI needs a
parameter decision (a macro aggregate is neither `VA`-by-activity nor a
`dfl`-like index) — deferred to the benchmark brick, with Lorenzo.

**D18 — UNSD governance extensions (small, one family).** Same snapshot,
recipe siblings of `UNSD.USE`: (a) **bunkers `051/052`** (needed by D14's
air/sea bands); (b) **stock changes flow `06`** (the inventory-change Y
anchors); (c) **households `1231` → the `CON` recipe** (residential Y
anchors + the D14 stationary term). Non-energy flow `11` deliberately not
imported (D12).

### Data build order (pilot critical path first)

For the IT×2023 pilot the LP needs, in nxbase: **D16** (set rows → B_ires),
**D18** (bunkers/stocks/households), **BACI.Q.Y23** full import (EXP
anchors — recipe exists, table registered at 0 rows), **D17** (VA
targets); and in nxsut: **WS-NET + v3.2 rebuild** (D15), then the bridge.
Everything else widens coverage but does not block the pilot: UNSD
Industrial Commodity Statistics (the biggest `x_obs` win — first after the
critical path), WDI + EDGAR (benchmarks; `EMBER.CI25` is already governed
and idle — KPI 3 at zero cost), Eurostat `nrg_bal_c` (EU quality upgrade),
FAOSTAT (food anchors + FBS).
