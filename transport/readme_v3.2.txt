Name: nxsut
Version: v3.2
Authors: LR, NG
Date: 2026 Aug
Build: transport service layer + UNSD-first supply mixes
Coverage: year 2023. 48 EXIOBASE Hybrid regions. 207 activities, 211
commodities (v3.1: 190 / 199). GHG satellite accounts.


WHAT v3.2 ADDS TO v3.1
======================

v3.1 was v3.0 (EMBER supply mixes, ENTSO-E electricity trade, Ghezzi steel/H2
routes) plus the BACI material trade update. v3.2 changes two things, both
upstream of any future nowcast:

  A. TRANSPORT SERVICE LAYER. Transport stops being a set of monetary service
     sectors and becomes a physical layer: the commercial transport sectors are
     split into freight and passenger children denominated in tonne-km and
     passenger-km; private mobility becomes household-operated vehicle
     activities producing a mobility service; the sectors' own internal
     logistics is externalised into its own activity and commodity.

  B. ELECTRICITY SUPPLY MIXES, UNSD-FIRST. The generation mix now comes from
     the UNSD Energy Statistics production view wherever it is coherent with
     EMBER, and from EMBER elsewhere. UNSD carries what EMBER cannot see:
     CHP plants, heat plants, autoproducers (rooftop PV included) and the
     by-fuel thermal detail.

Everything both changes consume is governed in nxbase and read through its
query API at generation time; the input chain stays open.


A. TRANSPORT SERVICE LAYER
==========================

Why. Energy statistics classify fuel by MODE (all road fuel in one bucket:
hauliers + every sector's own trucks + private cars). The economic table
classifies by USER (the haulier sector buys only its own fuel; own-account
fuel sits inside each industry; household fuel is final demand). Any split of
an energy balance onto the economic structure was therefore a repartition, not
a model. After v3.2 the two perimeters coincide: all road fuel sits in
transport-family columns, and the industry columns keep process, heating and
off-road fuel only - which is exactly what the UNSD industry rows contain.

NEW ACTIVITIES (17)
  Road freight transport                    Private car transport, gasoline
  Road passenger transport                  Private car transport, diesel
  Rail freight transport                    Private car transport, LPG
  Rail passenger transport                  Private car transport, natural gas
  Sea and coastal freight transport         Private car transport, electric
  Sea and coastal passenger transport       Private motorcycle transport
  Inland water freight transport            Own-account road freight transport
  Inland water passenger transport
  Air freight transport
  Air passenger transport

NEW COMMODITIES (12), with their units
  Road freight transport services                            Mtkm
  Road passenger transport services                          Mpkm
  Rail freight transport services                            Mtkm
  Rail passenger transport services                          Mpkm
  Sea and coastal freight transport services                 Mtkm
  Inland water freight transport services                    Mtkm
  Own-account road transport                                 Mtkm
  Private road mobility                                      Mpkm
  Sea and coastal passenger transport services               Meuro
  Inland water passenger transport services                  Meuro
  Air freight transport services                             Meuro
  Air passenger transport services                           Meuro

World outputs of the physical children (2023): road freight 13,377 Gtkm,
own-account road freight 2,164 Gtkm, road passenger 2,737 Gpkm, rail
passenger 3,286 Gpkm, rail freight 7,256 Gtkm, sea and coastal freight
5,579 Gtkm, inland-waterway freight 3,420 Gtkm, private mobility 16,032
Gpkm.

The parents "Other land transport" and "Transport via railways" (and their
commodities) remain in the grid with zero output - folding them away is
blocked by MARIO's unit check (MEUR parent vs Mtkm child) and is cosmetic.
"Transport via pipelines" was already a separate sector in EXIOBASE and is
untouched; it stays monetary (see "what stayed monetary").

Move B - splitting the commercial transport sectors
---------------------------------------------------
Order matters: the column is split in MEUR FIRST, then each child is
re-denominated into its own physical unit. Splitting first in a physical unit
is impossible (pkm and tkm do not add up).

  1. Monetary split key = observed turnover by NACE class, from Eurostat SBS
     (governed as ESTAT.SBSH49). Fallback chain, per cell, with provenance:
     SBS observed -> OECD SDBS (adds KOR) -> median implicit price x observed
     volumes -> median of the observed countries. The last tier is not
     optional: an MRSUT has one sector list for every region, so "no split"
     does not exist - Rest-of-World aggregates get the declared median
     structure.
     Coverage of the top tier (country-blocks observed in SBS): road 33,
     rail 13, sea 16, inland waterways 13, air 15.

  2. Re-denomination: output = the observed physical volume Q, coefficients
     divided by Q. The implicit price M/Q is a DIAGNOSTIC OUTPUT, never an
     input; a child whose implicit price lands outside its plausibility band
     keeps the monetary denomination. Observed Q per child (number of
     regions): road freight 38, rail passenger 37, rail freight 37, air
     freight 40, inland-waterway freight 22, road passenger 19, sea freight
     15. Where Q is missing the child is scaled by the median implicit price
     of that child type, so the commodity keeps ONE unit worldwide.

  3. Carve, do not rebuild. The liquid-fuel rows are re-split bottom-up
     (vehicle-km x fuel intensity); every other input and value added is
     inherited pro-quota from the parent. Nothing in the parent's recipe is
     thrown away - the reason a full bottom-up reconstruction was rejected.

  4. Use side: final purchases (households, government) go to the passenger
     child, intermediate purchases to the freight child, with a declared 10%
     proportional allowance that also covers business travel; each parent use
     row is then closed with a small per-row IPF so both the child totals and
     the original cells are preserved. Negative cells (inventory changes) are
     split by the supply shares outside the IPF - mixed signs break iterative
     scaling.

  Acceptance: re-aggregating the children reproduces the parent exactly
  (max error 7.5e-09 across 48 regions); Italy's road freight child lands at
  127.8 of 129.1 Gtkm observed (99%).

Move A - private mobility as activities
---------------------------------------
Six household-operated activities (five car powertrains + motorcycles) supply
one commodity, "Private road mobility" [Mpkm], bought by households. The
households' motor-fuel purchases move out of final demand into the activities'
use columns, and their combustion emissions move with them.

  Data. Vehicle-km per powertrain = observed car passenger-km (ITF/Eurostat)
  / occupancy x car-park share by motor energy (Eurostat road_eqs_carpda,
  first year with both petrol and diesel reported, as the 2011 proxy). Fuel
  intensities per powertrain from FULFILL_MARIO (Golinucci et al. 2025,
  Apache 2.0), REF baseline 2011, summed over origin regions.

  Caps. The fuel moved per carrier is capped by what households actually buy:
  household diesel, LPG, gas and electricity also serve heating and home uses,
  so the reroute never exceeds the bottom-up transport demand, and the vehicle
  activity is rescaled to the cap. Consequence worth knowing: in Italy the cap
  lands at 85% of the observed car passenger-km - the missing 15% is the
  company-car share, whose fuel sits in the sectors, not in final demand. The
  perimeter emerges from the data instead of being assumed.

  Emissions. Household driving combustion is re-attributed from the household
  satellite to the activities with IPCC CO2 emission factors (gasoline 3.07,
  diesel 3.17, LPG 3.02, natural gas 2.75 t CO2 per t fuel; CO2 only in v0).
  Conservation is exact: nothing is created or lost, only re-attributed.

  Where no car passenger-km is observed (24 of 48 regions) the vehicle-km are
  synthesised by inverting the households' gasoline purchases - declared.

Move C - own-account road freight
----------------------------------
The sectors' internal logistics becomes one activity per region,
"Own-account road freight transport", producing "Own-account road transport"
[Mtkm] which each sector buys back. This is the SNA externalisation of an
ancillary activity, done with data rather than by assumption, and it is what
makes the UNSD alignment exact.

  Volume: observed own-account tonne-km (ITF, 27 regions; elsewhere the
  EU-observed own-account share of 15.4% applied to the hire-and-reward
  volume). Fuel = tonne-km / load factor x HGV intensity, diesel only.

  Which sectors it is taken from: allocation weight = the column's diesel x a
  declared propensity per sector class, seeded by the OBSERVED own-account
  share per goods type (Eurostat road freight by NST2007 group: removals 44%,
  waste 28%, construction minerals 19%, agri-food ~18%, metals 9.6%,
  chemicals 8.4%, transport equipment 5.9%). Heavy and process industry is
  excluded from the pool entirely: its diesel cells are feedstock- and
  process-grade, not fleet fuel (the Polish chemicals column alone holds 2.4
  Mt of diesel and dominated any small positive weight). Mining, agriculture
  and construction are damped because their diesel is largely off-road
  (tractors, haul trucks, site equipment) - which must stay in the sector,
  since the UNSD industry rows keep it there too.

  Caps and honesty: at most 80% of a fleet-dominated cell and 50% elsewhere
  can be extracted, with waterfall redistribution. What the columns cannot
  host is NOT forced: it stays embedded and is reported (Poland and Great
  Britain, 9% each). World own-account output lands at 2.17 Gtkm = 13.9% of
  total road tonne-km, against the 15.4% observed in the EU - the aggregate
  closes on the statistics without having been forced to.


B. ELECTRICITY SUPPLY MIXES, UNSD-FIRST
=======================================

Per country the generation mix comes from UNSD.GEN where the arbitrated
selection allows, from EMBER otherwise; for years UNSD does not cover the
blend degrades to pure EMBER automatically. For 2023, 172 of 199
country-years come from UNSD.

  Selection (step 0, two stages, both reproducible):
   1. mix distance: total variation between the UNSD and EMBER 9-family mixes.
      UNSD if <= 0.05, EMBER if > 0.15, review in between. Level differences
      only flag - the consumed object is the mix.
   2. implied efficiencies arbitrate the review pool: fuel input to plants
      (UNSD 088x, converted with the snapshot's own calorific factors) over
      electricity and heat output (015C/016C), by plant type and by fuel.
      A country whose implied efficiencies are physically plausible is
      internally coherent and switches to UNSD; one outside the bands stays
      on EMBER. Final selection: 173 UNSD, 32 EMBER, every major emitter on
      UNSD. Sanity of the arbiter itself: coal electric-only efficiency
      0.34-0.37 and gas 0.44-0.47 across IT/US/JP/GB - textbook values,
      obtained with no convention (renewables and nuclear never enter the
      ratio, since they have no fuel input).

  What this buys: CHP is visible (share of thermal generation from CHP
  plants: PL 0.96, IT 0.60, FR 0.43, DE 0.40), autoproduction is visible
  (rooftop PV is half of Italian solar), and waste-to-energy is separated.


WHAT STAYED MONETARY, AND WHY
=============================

Re-denomination happens only where an honest physical denominator exists:

  - pipeline transport: the sector's turnover covers gas and oil transport
    while the observed tonne-km cover only part of the network - the implicit
    price lands far out of band, so the sector keeps MEUR;
  - passenger air and passenger water transport: no open source publishes
    passenger-km for them (only passengers carried), so those children keep
    MEUR;
  - AIR FREIGHT, on measurement. The World Bank tonne-km count belly cargo
    flown by PASSENGER airlines, while the SBS freight class is dedicated
    cargo carriers only. The perimeters do not match and the implied prices
    say so - DE 1.25, IT 0.14, US 0.07 EUR/tkm, a three-order spread where a
    coherent measure would cluster - so the air block splits in MEUR only,
    which is what its monetary key supports. Re-denominating it needs an
    airline-level tonne-km series that separates dedicated freighters, or a
    revenue split that reassigns belly-cargo revenue;
  - everything outside transport is untouched.

  Rule of thumb applied throughout: the OBSERVED VOLUME ALWAYS WINS. When a
  child's implied price is far from its own median, that is almost always the
  monetary side misbehaving (SBS coverage, transit traffic, a class that also
  does other things) - substituting the volume would replace a good
  observation with a value derived from the suspect one. Such cases are
  flagged for the radar (39 of 208 child-country cells) and left alone. A
  volume is synthesised only where none is observed, so that each commodity
  keeps one unit worldwide.


KNOWN LIMITATIONS (v0 of the layer)
===================================

  1. Own-account footprints are identical across countries because the recipe
     is country-invariant in v0 (one default load factor, one intensity).
     Refinement: wire the per-country observed own-account load factors.
  2. The road passenger child implies a fuel economy of roughly 10 L/100 km,
     too low for a bus: its passenger-km denominator includes trolleybuses
     (electric) and its share of the parent's liquid fuel is driven by a
     bottom-up key dominated by heavy goods vehicles. Read it as "road public
     transport within the commercial sector perimeter", not as a bus.
  3. Per-tonne-km footprints of the commercial children are NOT comparable
     across countries yet: the in-sector share of trucking fuel varies a lot
     (direct emissions of road freight: IT 33, DE 16, PL 1.5 gCO2/tkm),
     because what Move C could extract depends on what the national column
     held.
  4. Emission factors are CO2-only in the re-attribution (CH4 and N2O are
     ~1-2% of road CO2e).
  5. Car gasoline and diesel share one combined liquid intensity (FULFILL
     reports them jointly); separating them is a job for the nowcast, which
     closes against the observed gasoline and diesel totals.
  6. International aviation and shipping perimeters differ between the
     economic sectors (which include international legs) and the observed
     inland volumes (territory-based); this is why their passenger children
     stay monetary and their freight children are checked against the
     implicit-price band before re-denomination.


DATA SOURCES (all governed in nxbase, all open)
===============================================

  ITF/OECD               passenger-km, tonne-km, vehicle-km by mode; the
                         hire-and-reward vs own-account split, worldwide
                         (CC BY 4.0)
  Eurostat transport     road passenger-km by vehicle type, rail
                         passenger-km, road freight tonne-km by type of
                         operation (CC BY 4.0)
  Eurostat SBS           turnover by NACE class H49/H50/H51 - the monetary
                         split key (CC BY 4.0)
  Eurostat road_go_ta_tg road freight tonne-km by goods type and operation -
                         the observed own-account propensity (CC BY 4.0)
  Eurostat road_eqs_carpda car fleet by motor energy - powertrain shares
                         (CC BY 4.0)
  World Bank             air freight tonne-km, ICAO-derived (CC BY 4.0)
  UNSD Energy Statistics fuel use by sector and generation by plant type,
                         producer and fuel (UNdata terms, open)
  EMBER                  electricity generation by technology (CC BY 4.0)
  FULFILL_MARIO          car fuel intensities by powertrain (Golinucci et al.
                         2025, Apache 2.0)
  NXTR.V0                the transport recipe inventory assembled from the
                         above and published as an nxbase source


REPRODUCING
===========

  gen_v3.ipynb, with NXSUT_YEAR / NXSUT_VERSION set (defaults 2025 / v3.2).
  The transport layer is one pipeline step, transport.pipeline
  .apply_transport_layer(db), applied after the furnace-gas block and before
  the supply-mix updates so the battery-electric car's electricity input joins
  the electricity pooling. Its inputs (split specification, propensity table,
  recipe master, step-0 selection) are committed under transport/data/ and
  nowcast/data/ in the nxsut repository.
