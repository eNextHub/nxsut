Name: nxsut
Version: v3.2
Authors: LR, NG
Date: 2026 Aug
Build: transport service layer + UNSD-first supply mixes
Coverage: year 2023. 48 EXIOBASE Hybrid regions. 203 activities, 207
commodities (v3.1: 190 / 199 — the layer adds 17 activities and 12
commodities and folds 4 of the 5 emptied parents of each into the fifth).
GHG satellite accounts.


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
  Sea and coastal passenger transport services               Mpkm
  Inland water passenger transport services                  Mpkm
  Air freight transport services                             Mtkm
  Air passenger transport services                           Mpkm

Every one of the twelve is physical: no transport commodity the layer
creates is denominated in money.

World outputs (2023): road freight 13,377 Gtkm, own-account road freight
2,164 Gtkm, road passenger 2,737 Gpkm, rail passenger 3,286 Gpkm, rail
freight 7,256 Gtkm, sea and coastal freight 5,579 Gtkm, inland-waterway
freight 3,420 Gtkm, private mobility 16,032 Gpkm, air passenger 4,844 Gpkm,
air freight 126 Gtkm, sea and coastal passenger 113 Gpkm, inland-waterway
passenger 16 Gpkm.

Two of those are checkable against published world totals and land where
they should: world air revenue passenger-km were ~5,100 Gpkm in 2011
(ICAO/IATA), against 4,844 here — 95%, the gap being the countries outside
the 48 EXIOBASE regions; and Italian air passenger-km come within 1.3% of
Eurostat's independent national series.

The five split parents (road, rail, sea, inland water, air) end up with zero
output. Four of them are FOLDED AWAY at the end of the layer into the fifth
("Other land transport" / "Other land transportation services"), which stays
in the grid as a single empty pair instead of five. The fold checks the
outputs really are zero before touching anything, so it is a numerical no-op.

The target is deliberately one of the empty parents and NOT a live sector.
MARIO carries zero-output items through an aggregation by stamping their
output with zero_output_epsilon (1e-30) so their coefficients survive, then
maps those labels through the aggregation and stamps the resulting label too.
Folding an empty item into a live one therefore drives the live sector's
output to 1e-30 as well. An earlier build folded the parents into the
transport residual category (63): sector 63 was annihilated in all 48
regions while every industry kept buying from it, the table lost its balance,
and the Leontief inverse started returning negative outputs across ~1500
activities — with negative GHG footprints for most transport sectors. The
pipeline now refuses any fold whose group is not entirely empty, and verifies
afterwards that no output outside the fold groups moved.

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
     input: a child whose implicit price lands outside its plausibility band
     is FLAGGED, not overridden — the observed volume wins, because it is
     the measured quantity (see limitation 7). Observed Q per child (number
     of regions): air passenger 41, air freight 40, road freight 38, rail
     passenger 37, rail freight 37, inland-waterway freight 22, sea
     passenger 20, road passenger 19, sea freight 15. Where Q is missing the
     child is scaled by the median implicit price of that child type (200 of
     ~480 cells, mostly the Rest-of-World aggregates and the small water
     sectors), so the commodity keeps ONE unit worldwide.

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

Every transport child produced by the split is now PHYSICAL. One sector is
not, and it is not one the split created:

  - TRANSPORT VIA PIPELINES keeps MEUR. It was already its own sector in
    EXIOBASE and the split leaves it alone. Its turnover covers gas and oil
    transport while the observed tonne-km cover part of the network only, so
    the implied price lands 10-20x above anything comparable - there is no
    honest denominator to move to;
  - everything outside transport is untouched.

The three that used to stay monetary were closed by finding the right
measurement rather than by assuming one:

  - AIR, both children, on CARRIER-based volumes. The earlier reading (that
    World Bank tonne-km count belly cargo of passenger airlines while the SBS
    class is dedicated freighters, so the perimeters cannot match) had the
    perimeter question the wrong way round: EXIOBASE's air sector is itself
    carrier-based and flies international legs - its jet fuel input is ~7.7x
    domestic aviation and ~1.07x domestic plus international bunkers. Against
    the carrier perimeter the implied prices converge ACROSS COUNTRIES
    instead of scattering (air freight IT 1.48 / DE 1.46 / FR 1.31 EUR/tkm),
    which is the evidence the re-denomination is sound. Read that as a
    cross-country statement only: the freight-to-passenger price ratio WITHIN
    a country is imposed at 10:1 by the revenue tonne-km key, not observed
    (see VALUATION below). Passenger-km
    come from ICAO's revenue passenger-km (free as UN SDG indicator 9.1.2)
    and, for base years the SDG series does not reach, from World Bank
    passengers carried x the observed ICAO average stage length - a ratio of
    two measured quantities, not an assumed constant. The freight/passenger
    key inside the block is REVENUE TONNE-KM: one passenger with baggage
    counts as 100 kg of payload, the standard ICAO/IATA/EN 16258/GLEC
    convention;
  - SEA AND COASTAL PASSENGER on Eurostat maritime passenger-km;
  - INLAND WATERWAY PASSENGER has no observation anywhere and never will:
    Regulation (EC) 1365/2006 Art. 2(4) explicitly excludes passenger vessels
    from collection, so Eurostat, ITF and the national offices publish
    nothing. Its volume is synthesised at the SEA passenger price - a declared
    proxy on a very small sector - so that the commodity keeps one unit
    worldwide.

  Rule of thumb applied throughout: the OBSERVED VOLUME ALWAYS WINS. When a
  child's implied price is far from its own median, that is almost always the
  monetary side misbehaving (SBS coverage, transit traffic, a class that also
  does other things) - substituting the volume would replace a good
  observation with a value derived from the suspect one. Such cases are
  flagged for the radar (56 of ~270 child-country cells) and left alone. The
  single exception is a coverage hole visible by cross-source comparison
  (see limitation 7). A volume is synthesised only where none is observed, so
  that each commodity keeps one unit worldwide.


WHAT THE BUILD MEASURES (acceptance, 2023 vintage)
==================================================

Structural, before any footprint is read:

  negative outputs      36 of 19.680 (the base EXIOBASE table carries ~40;
                        they are its own artefacts - Estonian lignite, US and
                        Indonesian refinery feedstocks, Chinese patent fuel)
  epsilon-scale outputs none

GHG AR6 footprint, weighted by output over every producing region, against
the literature band:

  Road freight transport                 51 g/tkm   [30-250]    OK
  Own-account road freight              147 g/tkm   [30-300]    OK
  Road passenger transport               35 g/pkm   [20-150]    OK
  Rail passenger transport               41 g/pkm   [10-150]    OK
  Rail freight transport                 24 g/tkm   [5-100]     OK
  Sea and coastal freight               144 g/tkm   [5-100]     OUT (see 8)
  Sea and coastal passenger             498 g/pkm   [50-800]    OK
  Inland water freight                   25 g/tkm   [10-120]    OK
  Inland water passenger                343 g/pkm   [50-800]    OK
  Air freight transport                1585 g/tkm   [300-2500]  OK
  Air passenger transport               173 g/pkm   [60-400]    OK
  Private car, gasoline                 144 g/pkm   [80-250]    OK  (0/48 out)
  Private car, diesel                   147 g/pkm   [80-250]    OK  (0/48 out)
  Private car, LPG                      126 g/pkm   [60-250]    OK  (0/10 out)
  Private car, natural gas               70 g/pkm   [40-200]    OK  (0/14 out)
  Private car, electric                  56 g/pkm   [0-200]     OK  (0/40 out)
  Private motorcycle                    105 g/pkm   [40-200]    OK  (0/9 out)

Sixteen of seventeen land inside their band. The exception is sea freight,
and it is a perimeter gap that is measured rather than mysterious
(limitation 8): divide it by the ~12x between the sector's carrier-based
work and its territorial tonne-km and it lands at ~12 g/tkm, in the middle
of the published range.

Electricity anchor (regression against v3.0): Italy "Electricity need"
93,1 tCO2eq/TJ = 335 gCO2eq/kWh, against ~358 in v3.0 — the shift the
UNSD-first supply mix is expected to produce, not a break.

Road fuel perimeter (Move C's own test, transport/check_fuel_balance.py).
All road motor fuel, whoever burns it, should sit in the road transport
family's columns; what a household bought beyond its bottom-up transport
demand stays in final demand, so the table gives a bracket. Against the
observed UNSD/IRES transaction 1221, liquid fuels only:

              activities   + households   observed 1221   ratio
  IT             19,7 Mt      24,3 Mt        33,0 Mt      0,60 - 0,74
  DE             33,2         45,4           49,5         0,67 - 0,92
  FR              2,9         33,9           43,9         0,07 - 0,77
  ES             12,3         16,1           29,3         0,42 - 0,55
  PL              7,0          9,7           22,4         0,31 - 0,43
  US            184,8        234,2          551,4         0,34 - 0,42
  CN            106,4        106,5          150,3         0,71
  JP             27,8         41,7           54,4         0,51 - 0,77

Two things to read here. The bracket is wide for France because Move A's
cap left most household fuel in final demand — the perimeter is right, the
attribution between activity and final demand is not yet. And the level
sits below the observation everywhere, most in the United States: the
table carries EXIOBASE's 2011 volumes against a 2021-23 observation, and
part of the gap is road fuel still sitting in industry columns that Move C's
propensity table did not reach. Closing that gap on the observed totals is
the NOWCAST's job, not this layer's: v3.2 fixes the STRUCTURE (who produces
what, in which physical unit), the level calibration comes after.


VALUATION: WHAT STAYS BASIC-PRICE, AND WHERE AN ASSUMPTION ENTERS
=================================================================

The table is at basic prices and stays there: nothing here revalues a
monetary flow, and taxes less subsidies on products keep their own factor
row. But re-denominating a service has two consequences on valuation that a
reader has to know about.

1. WHAT THE USE MATRIX NO LONGER SAYS. For a re-denominated commodity the
   monetary value of each use flow is no longer readable: the cell reads
   "so many tonne-km", not "so many Meuro". EXIOBASE hybrid already lives
   with this for materials — steel is in tonnes — and MARIO handles the mix,
   but it does mean the basic-to-purchaser reconciliation, deflation and any
   price analysis can no longer be done ON the transport rows. Before v3.2
   they could.

   Worth knowing WHY transport rows are large in the first place: this table
   has trade and transport margins REALLOCATED, so the transport of the
   goods a sector buys shows up as that sector's own purchase of transport
   services. That is why construction is the second largest buyer of sea
   freight worldwide and public administration the fifth — not because
   building sites charter ships, but because the margin on everything heavy
   they buy is booked as transport.

2. WHERE AN ASSUMPTION ON RELATIVE BASIC PRICES ENTERS: AIR, AND ONLY AIR.
   The air block splits its REVENUE with the same revenue-tonne-km key that
   splits its fuel, because the SBS class boundary (dedicated freighters)
   does not describe children defined by the work done, belly cargo
   included — and belly cargo revenue is booked by the passenger airline.
   The arithmetic consequence, measured on the built table: the
   freight-to-passenger implied price ratio is 9,998 (min 9,971, max 10,065
   over 40 countries). That 10 is the 100 kg convention, imposed, not
   observed. Air freight and air passenger in this table therefore carry
   independent information about their relative physical WORK, and none
   about their relative VALUE.
   (The order of magnitude is not absurd — real air cargo rates run
   1,5-3 EUR/tkm against passenger yields of 0,10-0,15 EUR/pkm — but
   plausible is not observed.)

   Road, rail and water keep the OBSERVED SBS revenue split, and their
   freight-to-passenger price ratios scatter accordingly (0,02 to 12,7):
   noisy, but information.

3. OWN-ACCOUNT ACTIVITIES HAVE ZERO VALUE ADDED by construction — the
   private car activities of Move A and the own-account road freight of
   Move C. That is the standard convention for own-account production, but
   it means those activities have no operating surplus and their implicit
   price is pure cost.


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
     economic sectors (which include international legs) and the
     territory-based inland volumes. Air is denominated on CARRIER-based
     volumes (ICAO/World Bank: the operator's country of registration), which
     is the perimeter EXIOBASE's air sector actually has - its jet fuel input
     is ~7.7x domestic aviation and ~1.07x domestic plus international
     bunkers. Sea and inland waterway keep territory-based volumes, so their
     implied prices are the least comparable of the set.
  7. The implicit price each re-denomination produces (child turnover over
     observed volume) is reported per country and checked against the
     cross-country median, but a value outside the band does NOT override the
     observation: the volume always wins, because it is the measured
     quantity. 56 of ~270 country-children are flagged; the extremes are
     small sectors where the monetary side covers more than the volume
     statistic does (Cyprus and Belgium sea passenger, Swiss inland
     waterways, Irish rail freight). Read the per-country footprint of those
     cells with the flag in hand.
     One class IS corrected, because it is a reporting hole rather than a
     difference: when two sources publish the same national total and one is
     more than fivefold smaller, the larger wins and the swap is declared.
     Exactly one cell qualifies (France bus/coach passenger-km: Eurostat
     publishes 51 Mpkm for 2011, ITF 54.702, and the two agree exactly for
     Germany and Spain).
  8. WATER TRANSPORT carries a perimeter gap that air does not, and it is the
     weakest point of the layer. EXIOBASE's sea sector burns the national
     fleet's bunkers, international legs included, while the only open
     tonne-km series (ITF coastal shipping) counts territorial coastal
     traffic. The table's world sea freight work is 6.521 Gtkm against
     roughly 81.000 Gtkm of real seaborne work in 2011 (UNCTAD, ~44.000 bn
     tonne-miles): the sector's intensity per tonne-km is therefore an upper
     bound by about an order of magnitude, and it is NOT comparable across
     countries — a country whose fleet works far from home (Greece) looks
     worse than one whose fleet is coastal. Air escaped this precisely
     because ICAO passenger-km and World Bank tonne-km are carrier-based and
     so match the sector; the CROSS-COUNTRY convergence of the air implied
     prices is the evidence (not the freight-to-passenger ratio, which the
     revenue tonne-km key imposes — see VALUATION).
     The v1 fix is the same move for sea: allocate world tonne-miles to
     countries by fleet ownership (UNCTAD merchant fleet, open) instead of
     using territorial traffic. It changes a major commodity's world total by
     more than an order of magnitude, so it is a decision to take explicitly
     rather than a patch to slip in.
  9. VOLUME CONCEPTS, AUDITED. The rule the layer needs is that numerator and
     denominator describe the same population: emissions in an IO table
     follow RESIDENCE (the resident operator's fuel, bought anywhere), so the
     physical work must be the resident operator's work, wherever performed.
     Checked source by source:
       air        carrier-based (ICAO, World Bank count by country of
                  operator registration)                              COHERENT
       road       Eurostat road_go is vehicle-registration based - its
                  tra_oper dimension carries cabotage and cross-trade,
                  i.e. work performed entirely abroad - and the recipe
                  takes tra_oper = TOTAL                              COHERENT
       rail       territorial, but trains are handed over at the border
                  and operators work at home                       ~ COHERENT
       sea, iww   territorial, operators work abroad                INCOHERENT
     The two that break are exactly the two whose operators routinely work
     outside their own territory. That is the rule seen from the other side.

     One residual on road: ITF is NOT a single concept. Of 29 countries
     comparable with Eurostat for 2011, 17 match to better than 0,5% (ITF
     republishes the Eurostat figure) but seven diverge by 5% or more, almost
     always downwards - Slovenia -87%, Netherlands -47%, Austria -40%,
     Denmark -25%, Norway -11% - which is the territorial signature in
     countries whose hauliers work abroad. The recipe takes Eurostat first,
     so the ~30 European countries are on the carrier basis; the 23 countries
     that only ITF covers (United States, China, Japan, India, Canada,
     Australia, Korea, Mexico, Türkiye and others) sit on whichever concept
     their national office reports, and the data cannot tell us which.


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

  transport/build_v32.py runs the same notebook cells headless and prints a
  negative-output report after every stage. Use it when a build has to be
  watched: nbconvert does not stream cell output, which is how a broken
  Leontief inverse shipped twice unnoticed.

CHECKING A BUILD
================

  transport/validate_v32.py [year] [version]
      Structural gate first — negative-output count against the ~40 the base
      EXIOBASE table carries, and a screen for outputs at 1e-30 scale (a
      sector annihilated by an aggregation) — then the GHG footprint of all
      17 transport activities against literature bands, averaged over every
      producing region, with p10/p50/p90 and the count outside the band.
      A negative or epsilon-scale output invalidates every footprint in the
      table, so nothing below the gate is worth reading until it is clean.

  transport/check_fuel_balance.py [year] [version]
      Move C's perimeter test: all road motor fuel, whoever burns it, should
      sit in the road transport family's columns, and that total should line
      up with the observed UNSD/IRES transaction 1221.
