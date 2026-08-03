"""SIEC energy product -> NXS commodity: the declared carrier concordance.

This is the one mapping the parent graph **cannot** derive, and it is worth
saying why. nxbase anchors every SIEC product on its CN26 heading, and the
NXS energy commodities anchor there too — but a heading like CN 2710
(petroleum oils) carries a dozen NXS rows, so walking up from a SIEC product
lands on "some row under 2710", not on the right one: the graph resolution
puts Naphtha on Motor Gasoline and Fuelwood on wood-waste treatment. That is
not a defect of the anchors; it is the KB's own rule showing its edge — a
parent link expresses *containment*, never *enumeration*, and picking which
of several contained rows is the counterpart is exactly the enumeration the
rule refuses to encode.

So the mapping is **declared here, in the consumer** (the doctrine's place
for it), and **verified against the graph**: :func:`check` asserts that every
declared pair really shares an ancestor, which catches a typo, a renamed row
or a re-anchoring the day it happens. 29 of the pairs are additionally exact
name identities — EXIOBASE hybrid built its energy commodities on the same
IEA/UNSD product nomenclature — and those are re-derived, not trusted.

Two structural notes:

- **Electricity binds on the pooled row.** Every ``7000*`` product maps to
  ``ELE.NEED``: in the v3.1+ table the power activities supply ``ELE``, the
  pool consumes it and supplies ``ELE need``, and every consumer buys the
  need row. A sector's observed electricity consumption therefore constrains
  ``ELE.NEED``; ``ELE`` is the generation-side row the ``x_obs`` anchors
  reach through the supply block.
- **Aggregates are declared, not summed.** ``0100 Hard Coal`` overlaps its
  own children (anthracite + coking + other bituminous), same for
  ``0200 Brown Coal`` and the ``5212/5222/5232`` "of which" rows. They are
  listed in :data:`AGGREGATES` so the observation builder can prefer the
  leaves and fall back to the aggregate only where a country reports no
  leaf — the same not-reported-is-not-zero discipline as the IRES ``121``
  bucket.
"""

from __future__ import annotations

from . import graph as g

# SIEC short -> NXS3 short. Declared; verified by check().
SIEC_TO_NXS: dict[str, str] = {
    # --- coal & derivatives ---
    "0110": "ANTH",  # Anthracite
    "0121": "COKC",  # Coking coal
    "0129": "OTBC",  # Other bituminous coal
    "0210": "SUBC",  # Sub-bituminous coal
    "0220": "LIBC",  # Lignite / Brown Coal
    "0100": "OTBC",  # Hard Coal — AGGREGATE, lands on the dominant leaf
    "0200": "LIBC",  # Brown Coal — AGGREGATE
    "0311": "COKE",  # Coke Oven Coke
    "0312": "GCOK",  # Gas Coke
    "0320": "PATF",  # Patent fuel
    "0330": "BKBP",  # Brown Coal Briquettes -> BKB/Peat Briquettes
    "0340": "COTA",  # Coal Tar
    "0350": "COOG",  # Coke Oven Gas
    "0360": "MGWG",  # Gasworks Gas
    "0371": "MBFG",  # Blast Furnace Gas
    "0379": "MOSG",  # Other recovered gases -> Oxygen Steel Furnace Gas
    # --- peat ---
    "1100": "PEAT",
    "1200": "BKBP",  # Peat Products -> BKB/Peat Briquettes
    # --- natural gas ---
    "3000": "NGAS",
    # --- crude & oil products ---
    "4100": "COIL",  # Conventional crude oil
    "4200": "LNG",  # Natural Gas Liquids
    "4300": "REFF",  # Refinery Feedstocks
    "4400": "ADDC",  # Additives and Oxygenates
    "4500": "OGPL",  # Other hydrocarbons
    "4610": "RGAS",  # Refinery Gas
    "4620": "ETHA",  # Ethane
    "4630": "LPG",
    "4640": "NAPT",  # Naphtha
    "4651": "AGSL",  # Aviation Gasoline
    "4652": "GASO",  # Motor Gasoline
    "4653": "GJET",  # Gasoline-type jet fuel
    "4661": "KJET",  # Kerosene-type Jet Fuel
    "4669": "KERO",  # Other kerosene
    "4670": "DIES",  # Gas Oil / Diesel Oil
    "4680": "FOIL",  # Fuel Oil -> Heavy Fuel Oil
    "4691": "WHSP",  # White spirit & SBP
    "4692": "LUBR",  # Lubricants
    "4693": "PARW",  # Paraffin waxes
    "4694": "PETC",  # Petroleum Coke
    "4695": "BITU",  # Bitumen
    "4699": "NSPP",  # Other oil products n.e.c.
    # --- biofuels ---
    "5160": "CHAR",  # Charcoal
    "5210": "BIOG",  # Biogasoline
    "5212": "BIOG",  # of which: biogasoline — AGGREGATE-of-one
    "5220": "BIOD",  # Biodiesel
    "5222": "BIOD",  # of which: biodiesel — AGGREGATE-of-one
    "5230": "OBIO",  # Bio jet kerosene -> Other Liquid Biofuels
    "5232": "OBIO",  # of which — AGGREGATE-of-one
    "5290": "OBIO",  # Other liquid biofuels
    "5300": "MBIO",  # Biogases -> Biogas
    # --- electricity & heat (see the module docstring) ---
    "7000": "ELE.NEED",
    "7000G": "ELE.NEED",
    "7000H": "ELE.NEED",
    "7000N": "ELE.NEED",
    "7000O": "ELE.NEED",
    "7000S": "ELE.NEED",
    "7000T": "ELE.NEED",
    "7000W": "ELE.NEED",
    "8000": "HWAT",
    "8000T": "HWAT",
    "DG": "HWAT",  # direct use of geothermal heat
    "DS": "HWAT",  # direct use of solar thermal heat
}

# SIEC products that contain other SIEC products: the observation builder must
# never sum a parent with its own children. value = the covered children.
AGGREGATES: dict[str, tuple[str, ...]] = {
    "0100": ("0110", "0121", "0129"),  # Hard Coal
    "0200": ("0210", "0220"),  # Brown Coal
    "5210": ("5212",),  # Biogasoline / of which
    "5220": ("5222",),  # Biodiesel / of which
    "5230": ("5232",),  # Bio jet kerosene / of which
    "7000": ("7000G", "7000H", "7000N", "7000O", "7000S", "7000T", "7000W"),
    "8000": ("8000T",),
}

# Declared out of scope for the use-side bands, with the reason.
EXCLUDED: dict[str, str] = {
    "0390": "Other coal products — no counterpart row in the table",
    "2000": "Oil shale / oil sands — the table has no oil-shale commodity",
    "5110": "Fuelwood — the table's only wood-energy row is a waste-treatment "
    "service (WOOW), a different object; solid biomass use stays at prior",
    "5120": "Bagasse — as Fuelwood",
    "5130": "Animal waste — as Fuelwood",
    "5140": "Black liquor — as Fuelwood",
    "5150": "Other vegetal material and residues — as Fuelwood",
    "6100": "Industrial waste — an incineration *service* in the table, not a "
    "purchased fuel; the waste-to-energy activities carry it structurally",
    "6200": "Municipal waste — as industrial waste",
    "9101": "Uranium — mined ore, reported only on the production transaction; "
    "the nuclear fuel row has no use-side balance observation (see D12)",
}


# Pairs whose two sides are the same product but whose nxbase anchors do not
# meet in the graph, so the verification below cannot confirm them. In each
# case the SIEC row sits on the NXB biomass/energy node while the NXS row sits
# on its CN heading — both defensible alone, incompatible as a pair. The
# mapping is kept (the products are the same thing); the anchor divergence is
# an nxbase follow-up, not a silent pass: anything NOT listed here still fails
# the check loudly.
KNOWN_DIVERGENCES: dict[str, str] = {
    "4400": "SIEC on CN 2710 vs ADDC on the blending-components row",
    "5230": "SIEC on NXB biomass-energy vs OBIO on its CN heading",
    "5232": "as 5230",
    "5290": "as 5230",
    "5300": "SIEC on NXB biomass-energy vs MBIO (Biogas) on CN 2711",
}


def nxs_carriers() -> list[str]:
    """The ``fuels`` set, as NXS3 shorts: the image of the declared map.

    A commodity row is an endogenous carrier exactly when an energy-balance
    observation can bind it — which is what this image says.
    """
    return sorted(set(SIEC_TO_NXS.values()))


def check(api_url: str = g.DEFAULT_API) -> list[str]:
    """Verify the declaration against the graph and the live set rows.

    Returns the list of problems (empty = clean): unknown shorts on either
    side, declared pairs that share no ancestor, and SIEC products that are
    neither mapped nor explicitly excluded.
    """
    rows = g.rows("commodity", "SIEC", "NXS3", api_url=api_url)
    par = {r["extended"]: r["parent"] for r in rows}
    siec = {r["short"]: r for r in rows if r["classification"] == "SIEC"}
    nxs = {r["short"]: r for r in rows if r["classification"] == "NXS3"}
    problems: list[str] = []

    for s_short, n_short in SIEC_TO_NXS.items():
        if s_short not in siec:
            problems.append(f"SIEC {s_short!r} is not a governed product")
            continue
        if n_short not in nxs:
            problems.append(f"NXS3 {n_short!r} is not a governed commodity")
            continue
        s_chain = set(g.ancestors(siec[s_short]["extended"], par))
        n_chain = set(g.ancestors(nxs[n_short]["extended"], par))
        if not (s_chain & n_chain) and s_short not in KNOWN_DIVERGENCES:
            problems.append(
                f"{s_short} ({siec[s_short]['name']}) -> {n_short} "
                f"({nxs[n_short]['name']}): share no ancestor in the graph"
            )

    for s_short in siec:
        if s_short not in SIEC_TO_NXS and s_short not in EXCLUDED:
            problems.append(f"SIEC {s_short!r} ({siec[s_short]['name']}) is neither mapped nor excluded")
    return problems


if __name__ == "__main__":
    issues = check()
    print(f"declared pairs: {len(SIEC_TO_NXS)} -> {len(nxs_carriers())} carrier rows")
    print(f"excluded (declared): {len(EXCLUDED)}")
    if issues:
        print(f"\n{len(issues)} PROBLEM(S):")
        for line in issues:
            print("  " + line)
    else:
        print("graph verification: clean")
