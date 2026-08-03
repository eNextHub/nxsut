"""Move B (c), stage 1 — assemble the split spec for all EXIOBASE regions.

Produces the full, inspectable **split specification** before any table
surgery: for each of the 49 EXIOBASE regions and each block, the per-child
shares by row class, with tier and provenance per cell. Stage 2 (the apply
script, MARIO env) reads this CSV and performs the deterministic split.

Row classes (road_pipe block: ROAD.FRT / ROAD.PAX / PIPE; rail: TRN.P / TRN.F):

- ``fuel_liquid`` — diesel/gasoline/biofuel rows of the parent column:
  bottom-up shares HGV ∝ (tkm ÷ load) × intensity, BUS ∝ (pkm ÷ occupancy)
  × intensity (NXTR defaults; per-country load factors from leg-1 where
  observed); PIPE gets 0 (pipelines pump with electricity/gas). Rail:
  TRN.P/TRN.F ∝ traffic units (same per-tu intensity, the leg-1 v0 rule).
- ``other`` — every other input + VA (electricity/gas rows included, v0
  declared: minor) **and the supply split**: the SBS tier chain
  (1 = ESTAT.SBSH49 observed; 2/4/5 = moveb_split_master.csv; 5 = SBS
  median for regions in neither, RoW included).
- ``Q`` — the re-denomination targets (Mpkm / Mtkm observed, Y11): BUS →
  pkm, HGV → tkm, TRN.P/F → pkm/tkm; PIPE stays MEUR (diagnostic-(a)
  verdict). Missing Q = the child keeps MEUR (declared, never invented).

Use-row note (balance): the final/intermediate use rule (households → pax,
industries → tkm, business-travel exception, pipe → gas/oil users) yields
row totals that need NOT match the supply split — the apply script closes
each parent use row with a **per-row IPF** (row targets = supply split ×
M, column targets = parent cells): deterministic, tiny, declared.

Output: ``transport/moveb_split_spec.csv``
(region, block, row_class, child, share, tier, provenance).
"""

from __future__ import annotations

import csv
import io
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
API = "http://127.0.0.1:8000"

EXIOBASE_REGIONS = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK", "GB", "NO", "CH", "TR", "RU", "CN", "US", "JP", "IN",
    "CA", "KR", "BR", "MX", "AU", "ID", "ZA", "TW",
    "WA", "WE", "WF", "WL", "WM",
]

# Water carries ONE child, not two. Splitting freight from passenger needs
# both sides measured the same way, and for water they cannot be: the fuel
# and the revenue of a shipping sector belong to the resident fleet wherever
# it sails, and the only per-country work observation on that basis (UNCTAD
# fleet x IMO world transport work) is cargo. No open source publishes the
# passenger-km of a country's resident ferry and cruise operators. Rather
# than split with one side on a different perimeter, water is denominated
# whole in tonne-km-equivalent, folding passengers in at 100 kg each — the
# ICAO/IATA/EN 16258/GLEC convention already used for the air block's fuel.
# Cost: sea passenger transport stops being a mode of its own, ~0,5% of world
# passenger mobility that we could not measure coherently anyway.
BLOCKS = {"road_pipe": ["ROAD.FRT", "ROAD.PAX", "PIPE"], "rail": ["TRN.P", "TRN.F"],
          "sea": ["SEA"], "iww": ["IWW"],
          "air": ["AIR.FRT", "AIR.PAX"]}
# core = the children whose absence means "confidential", not "zero"
CORE = {"road_pipe": ["ROAD.FRT", "ROAD.PAX"], "rail": ["TRN.P", "TRN.F"],
        "sea": ["SEA"], "iww": ["IWW"],
        "air": ["AIR.FRT", "AIR.PAX"]}
SBS_MAP = {
    "H.49.41": ("road_pipe", "ROAD.FRT"), "H.49.42": ("road_pipe", "ROAD.FRT"),
    "H.49.31": ("road_pipe", "ROAD.PAX"), "H.49.33": ("road_pipe", "ROAD.PAX"),
    "H.49.39": ("road_pipe", "ROAD.PAX"), "H.49.50": ("road_pipe", "PIPE"),
    "H.49.1": ("rail", "TRN.P"), "H.49.20": ("rail", "TRN.F"),
    # water and air (SBS Rev-2 classes == NACE 2.1 classes here)
    "H.50.10": ("sea", "SEA"), "H.50.20": ("sea", "SEA"),
    "H.50.30": ("iww", "IWW"), "H.50.40": ("iww", "IWW"),
    "H.51.10": ("air", "AIR.PAX"), "H.51.21": ("air", "AIR.FRT"),
}
# volumes for Q and fuel shares: (source, activity) per (block, child); first
# spec with data wins (plausibility rule from diagnostic a: ESTAT can have
# coverage holes -> ITF fallback and vice versa).
VOLUMES = {
    ("road_pipe", "ROAD.FRT"): [
        ("Eurostat road freight by operation (tkm)", "Road freight transport - hire and reward"),
        ("International Transport Forum", "Road freight transport - hire and reward"),
        ("International Transport Forum", "Road freight transport (total)"),
    ],
    ("road_pipe", "ROAD.PAX"): [
        ("Eurostat road passenger performance (pkm)",
         "Road passenger transport - buses, coaches and trolleys"),
        # ITF names this exactly like Eurostat does; the old label
        # ("... buses and coaches") matched nothing, so the fallback never
        # fired and France kept Eurostat's 51 Mpkm coverage fragment
        ("International Transport Forum",
         "Road passenger transport - buses, coaches and trolleys"),
    ],
    ("rail", "TRN.P"): [
        ("Eurostat rail passenger transport (pkm)", "Rail passenger transport"),
        ("International Transport Forum", "Rail passenger transport"),
    ],
    ("rail", "TRN.F"): [("International Transport Forum", "Rail freight transport")],
    # Inland waterways: ITF territorial tonne-km. Barges do cross borders —
    # a Dutch barge working the German Rhine is German tonne-km but Dutch
    # fuel — so this is the same perimeter gap the sea block has, at a much
    # smaller scale and with no residence-based source to close it. Declared.
    ("iww", "IWW"): [("International Transport Forum",
                      "Inland waterways freight transport")],
    ("air", "AIR.FRT"): [("World Bank air freight (tonne-km)",
                          "H.51.21 Freight air transport")],
    # SEA and AIR.PAX are derived, not plain lookups: see
    # sea_transport_work (residence basis) and air_passenger_pkm.
}
# ICAO reference year for the stage length (first year of the SDG series)
ICAO_REF = "Y17"
# ICAO's own conversion when no operator factor is available: one passenger
# (with baggage) counts as 100 kg of payload — so 1 Mpkm = 0.1 Mtkm.
PAX_TONNE = 0.1
# base year of the table, the IMO study's base year, and the nautical mile
BASE_PERIOD, IMO_REF, NM_KM = "Y11", "Y18", 1.852
# NXTR v0 recipe constants for the liquid-fuel bottom-up shares.
# how far apart two sources for the same national total may be before the
# smaller one is read as a coverage hole rather than a measurement difference
COVERAGE_FACTOR = 5.0
INT_HGV, INT_BUS = 2.7e-4, 2.5e-4       # t/vkm
LOAD_DEFAULT, OCC_BUS = 10.0, 15.0      # tkm/vkm, pkm/vkm


def fetch_api(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def air_passenger_pkm(fetch) -> dict[str, float]:
    """Air passenger-km per region for the base year, in Mpkm.

    ICAO publishes passenger-km only from 2017 (UN SDG 9.1.2); the World
    Bank publishes passengers carried, same ICAO origin, back to 1990. The
    base-year figure is therefore
        pkm(Y11) = passengers(Y11) x [pkm(Y17) / passengers(Y17)]
    i.e. the observed passengers scaled by the observed average stage
    length — a ratio of two measurements, not an assumed constant. Both
    series are carrier-based, which is the perimeter of the EXIOBASE air
    sector (its jet fuel is ~7.7x domestic aviation).
    """
    pax: dict[tuple[str, str], float] = {}
    for r in fetch({"parameter": "Total output",
                    "source": "World Bank air passengers carried",
                    "limit": "100000"}):
        parts = r["item_1"].split("-")
        if len(parts) == 4:
            pax[(parts[2], parts[3])] = float(r["value"])
    pkm_ref: dict[str, float] = {}
    for r in fetch({"parameter": "Total output",
                    "source": "ICAO air passenger-km 2017-2024", "limit": "100000"}):
        parts = r["item_1"].split("-")
        if len(parts) == 4 and parts[3] == ICAO_REF:
            pkm_ref[parts[2]] = float(r["value"])
    out: dict[str, float] = {}
    for region, pkm17 in pkm_ref.items():
        p17 = pax.get((region, ICAO_REF), 0.0)
        p11 = pax.get((region, "Y11"), 0.0)
        if p17 > 0 and p11 > 0:
            stage_km = pkm17 / p17
            out[region] = p11 * stage_km / 1e6          # -> Mpkm
    print(f"air pkm derivate: {len(out)} regioni "
          f"(stage length mediana {sorted(pkm_ref[r] / pax[(r, ICAO_REF)] for r in out)[len(out) // 2]:.0f} km)")
    return out


def sea_transport_work(fetch) -> dict[str, float]:
    """Maritime work of each country's resident fleet, base year, in Mtkm.

    Composed from three governed sources, because no single one has it:
    the Fourth IMO GHG Study for the world level of transport work, UNCTAD
    seaborne trade to carry that level from the study's 2018 base to ours,
    and UNCTAD's fleet by beneficial ownership for each country's share.

    Beneficial ownership is the point: it is the economy commercially
    responsible for the vessel, which is the residence concept the table
    needs, and deliberately not the flag (Panama and Liberia would
    otherwise own a third of world shipping). Territorial tonne-km measure
    a different thing — work done on a country's coast, by anyone — and ITF
    reports none at all for Greece, whose fleet is the world's largest.

    The fleet series starts in 2014, so an earlier base year borrows the
    earliest shares. Fleet ownership moves slowly; it is still an
    approximation.
    """
    world = sum(float(r["value"]) for r in fetch(
        {"parameter": "Total output",
         "source": "Fourth IMO GHG Study 2020 — world transport work",
         "limit": "1000"}))
    if world <= 0:
        raise SystemExit("nxbase has no IMO world transport work (source IMO.GHG4)")
    world *= NM_KM                                      # Mtnm -> Mtkm

    loaded: dict[str, float] = defaultdict(float)
    for r in fetch({"parameter": "Total output",
                    "source": "UNCTAD seaborne trade, goods loaded", "limit": "200000"}):
        parts = r["item_1"].split("-")
        if len(parts) == 4:
            loaded[parts[3]] += float(r["value"])
    if not {BASE_PERIOD, IMO_REF} <= set(loaded):
        raise SystemExit(f"UNCTAD seaborne trade covers neither {BASE_PERIOD} nor {IMO_REF}")
    world *= loaded[BASE_PERIOD] / loaded[IMO_REF]

    dwt: dict[str, dict[str, float]] = defaultdict(dict)
    for r in fetch({"parameter": "Stock",
                    "source": "UNCTAD merchant fleet by beneficial ownership",
                    "limit": "200000"}):
        parts = r["item_1"].split("-")
        if len(parts) == 4:
            dwt[parts[3]][parts[2]] = float(r["value"])
    pick = BASE_PERIOD if BASE_PERIOD in dwt else sorted(dwt)[0]
    fleet = dwt[pick]
    total = sum(fleet.values())
    out = {site: world * v / total for site, v in fleet.items()}
    print(f"lavoro marittimo per residenza: {len(out)} paesi, mondo "
          f"{world / 1e6:,.1f} mld tkm (quote flotta {pick})")
    return out


def main() -> None:
    # --- tier 1: SBS shares per country (Y11) ---
    sbs: dict[tuple[str, str, str], float] = defaultdict(float)
    for r in fetch_api({"parameter": "Total output",
                        "source": "Eurostat SBS transport turnover (H49-H51)",
                        "limit": "100000"}):
        parts = r["item_1"].split("-")
        if len(parts) == 4 and parts[3] == "Y11" and parts[0][2:] in SBS_MAP:
            block, child = SBS_MAP[parts[0][2:]]
            sbs[(parts[2], block, child)] += float(r["value"])

    def sbs_shares(iso2: str, block: str) -> dict[str, float] | None:
        if not all((iso2, block, c) in sbs for c in CORE[block]):
            return None
        vals = {c: sbs.get((iso2, block, c), 0.0) for c in BLOCKS[block]}
        tot = sum(vals.values())
        return {c: v / tot for c, v in vals.items()} if tot > 0 else None

    # --- tier 5: SBS medians (core-reporting countries only) ---
    shares5: dict[str, dict[str, float]] = {}
    for block, children in BLOCKS.items():
        per_child: dict[str, list[float]] = defaultdict(list)
        for iso2 in {s for (s, b, _) in sbs if b == block}:
            sh = sbs_shares(iso2, block)
            if sh:
                for c, v in sh.items():
                    per_child[c].append(v)
        med = {c: statistics.median(v) for c, v in per_child.items()}
        norm = sum(med.values())
        shares5[block] = {c: v / norm for c, v in med.items()}

    # --- tiers 2/4/5: the non-SBS master ---
    master: dict[tuple[str, str, str], tuple[float, str, str]] = {}
    with open(HERE / "data" / "moveb_split_master.csv") as f:
        for r in csv.DictReader(f):
            master[(r["country"], r["block"], r["child"])] = (
                float(r["share"]), r["tier"], r["provenance"])

    air_pkm = air_passenger_pkm(fetch_api)
    sea_work = sea_transport_work(fetch_api)

    # --- volumes (Y11) for Q and fuel shares ---
    volume: dict[tuple[str, str, str], tuple[float, str]] = {}
    by_src: dict[tuple[str, str, str, str], float] = defaultdict(float)
    sources = sorted({s for specs in VOLUMES.values() for s, _ in specs})
    for src in sources:
        for r in fetch_api({"parameter": "Total output", "source": src,
                            "limit": "200000"}):
            parts = r["item_1"].split("-")
            if len(parts) == 4 and parts[3] == "Y11":
                by_src[(src, r["i1_name"], parts[2], parts[3])] += float(r["value"])
    for iso2, q in air_pkm.items():
        if iso2 in EXIOBASE_REGIONS:
            volume[(iso2, "air", "AIR.PAX")] = (q, "WB pax x ICAO stage length")
    for iso2, q in sea_work.items():
        if iso2 in EXIOBASE_REGIONS:
            volume[(iso2, "sea", "SEA")] = (
                q, "IMO world transport work x UNCTAD fleet share (residence)")
    swapped: list[tuple] = []
    for (block, child), specs in VOLUMES.items():
        for iso2 in EXIOBASE_REGIONS:
            cands = []
            for src, act in specs:
                q = by_src.get((src, act, iso2, "Y11"), 0.0)
                if q > 0:
                    label = "ESTAT" if "Eurostat" in src else "ITF"
                    note = "" if "hire" in act or "total" not in act else " (total: hire n/a)"
                    cands.append((q, label + note))
            if not cands:
                continue
            q, prov = cands[0]                        # source priority
            # Coverage arbitration. Two sources measuring the same national
            # total can differ by a few per cent (rounding, vintage), never by
            # a factor: a total that is many times SHORT is a reporting hole —
            # a country publishing one vehicle category instead of all — while
            # no statistical office over-reports a total fivefold. So when a
            # later source is much larger, it wins, and the swap is declared.
            # France's bus/coach pkm is the case that forced this: Eurostat
            # publishes 51 Mpkm for 2011, ITF 54.702 (and the two agree
            # exactly for Germany and Spain).
            wide = max(cands, key=lambda t: t[0])
            if wide[0] > q * COVERAGE_FACTOR:
                swapped.append((iso2, child, round(q, 1), round(wide[0], 1), prov, wide[1]))
                q, prov = wide[0], wide[1] + " (buco di copertura nella prima fonte)"
            volume[(iso2, block, child)] = (q, prov)
    if swapped:
        print(f"volumi sostituiti per copertura ({len(swapped)}):", flush=True)
        for iso2, child, small, big, p_small, p_big in swapped:
            print(f"    {iso2} {child:9} {p_small} {small:,.1f} -> {p_big} {big:,.1f}",
                  flush=True)

    # per-country observed HGV load factors (leg 1), default otherwise
    load: dict[str, float] = {}
    with open(HERE / "data" / "derived_recipes_v0.csv") as f:
        for r in csv.DictReader(f):
            if r["tech"] == "HGV" and r["coef"] == "load_factor_total" and r["year"] == "Y11":
                load[r["country"]] = float(r["value"])

    rows_out: list[dict] = []

    def emit(region: str, block: str, row_class: str, child: str, share: float,
             tier: str, prov: str) -> None:
        rows_out.append(dict(region=region, block=block, row_class=row_class,
                             child=child, share=round(share, 4), tier=tier,
                             provenance=prov))

    tier_count: dict[str, int] = defaultdict(int)
    for region in EXIOBASE_REGIONS:
        for block, children in BLOCKS.items():
            # -- 'other' (inputs + VA + supply): SBS chain --
            sh = sbs_shares(region, block)
            if sh:
                tier, prov = "1-SBS", "ESTAT.SBSH49 Y11 observed shares"
            elif any((region, block, c) in master for c in children):
                sh = {c: master[(region, block, c)][0] for c in children
                      if (region, block, c) in master}
                tier = master[(region, block, children[0])][1] if (
                    region, block, children[0]) in master else "master"
                prov = "moveb_split_master.csv (see per-cell tiers there)"
            else:
                sh = shares5[block]
                tier, prov = "5-median", "SBS Y11 median shares (RoW / no data)"
            if block == "air":
                # AIR is the one block where the monetary key must ALSO be
                # physical. Belly cargo is freight work flown on passenger
                # aircraft, and its revenue is booked by the passenger airline,
                # so the SBS class boundary (dedicated freighters only) does not
                # describe our children, which are defined by the WORK done.
                # Splitting revenue and costs on the same tonne-km-equivalent
                # basis as the fuel keeps the child coherent: ~a fifth of the
                # revenue and ~a fifth of the fuel, against its own tonne-km.
                w_pax = volume.get((region, "air", "AIR.PAX"), (0.0, ""))[0] * PAX_TONNE
                w_frt = volume.get((region, "air", "AIR.FRT"), (0.0, ""))[0]
                if w_pax + w_frt > 0:
                    tot_w = w_pax + w_frt
                    sh = {"AIR.PAX": w_pax / tot_w, "AIR.FRT": w_frt / tot_w}
                    tier = "4-tonne-km-equivalent"
                    prov = ("air split on revenue tonne-km (passengers at 100 kg, "
                            "ICAO convention): the SBS class covers dedicated "
                            "freighters only, our children cover the work")
            for c, v in sh.items():
                emit(region, block, "other", c, v, tier, prov)
            tier_count[f"{block}:{tier.split('-')[0]}"] += 1

            # -- fuel_liquid: bottom-up shares --
            if block == "road_pipe":
                tkm = volume.get((region, "road_pipe", "ROAD.FRT"), (0.0, ""))[0]
                pkm = volume.get((region, "road_pipe", "ROAD.PAX"), (0.0, ""))[0]
                if tkm > 0 or pkm > 0:
                    f_hgv = tkm / load.get(region, LOAD_DEFAULT) * INT_HGV
                    f_bus = pkm / OCC_BUS * INT_BUS
                    tot = f_hgv + f_bus
                    emit(region, block, "fuel_liquid", "ROAD.FRT", f_hgv / tot,
                         "4-bottom-up", "vkm x NXTR intensity (liquid fuels; PIPE=0)")
                    emit(region, block, "fuel_liquid", "ROAD.PAX", f_bus / tot,
                         "4-bottom-up", "vkm x NXTR intensity (liquid fuels; PIPE=0)")
                    emit(region, block, "fuel_liquid", "PIPE", 0.0,
                         "4-bottom-up", "pipelines pump with electricity/gas")
                else:
                    for c, v in sh.items():
                        emit(region, block, "fuel_liquid", c, v, "5-fallback",
                             "no volumes: fuel follows the 'other' shares (declared)")
            elif block == "rail":
                p = volume.get((region, "rail", "TRN.P"), (0.0, ""))[0]
                fq = volume.get((region, "rail", "TRN.F"), (0.0, ""))[0]
                if p > 0 or fq > 0:
                    emit(region, block, "fuel_liquid", "TRN.P", p / (p + fq),
                         "4-bottom-up", "traffic units (same per-tu intensity, leg-1 v0)")
                    emit(region, block, "fuel_liquid", "TRN.F", fq / (p + fq),
                         "4-bottom-up", "traffic units (same per-tu intensity, leg-1 v0)")
                else:
                    for c, v in sh.items():
                        emit(region, block, "fuel_liquid", c, v, "5-fallback",
                             "no volumes: fuel follows the 'other' shares (declared)")
            else:
                # Water and air: fuel follows PHYSICAL WORK, not revenue. Ships
                # and aircraft have no vehicle-km statistics, but passenger and
                # freight work share one vehicle, and the aviation and freight
                # accounting standards (ICAO DATA+, IATA RP 1726, EN 16258,
                # GLEC) allocate that fuel on a mass basis: a passenger counts
                # as 100 kg including baggage, so 1 Mpkm = 0.1 Mtkm-equivalent.
                # Splitting by revenue instead would give ferries and airlines'
                # passenger side most of the fuel — passenger revenue per unit
                # of physical work is an order of magnitude higher than
                # freight's — and produce absurd emission intensities.
                pax_c = next((c for c in children if c.endswith("PAX")), None)
                frt_c = next((c for c in children if c.endswith("FRT")), None)
                w_pax = volume.get((region, block, pax_c), (0.0, ""))[0] * PAX_TONNE
                w_frt = volume.get((region, block, frt_c), (0.0, ""))[0]
                if len(children) == 1:
                    # water: one child, so the whole liquid-fuel row is its own
                    emit(region, block, "fuel_liquid", children[0], 1.0,
                         "4-single-child", "one child on the block: nothing to split")
                elif w_pax + w_frt > 0:
                    tot_w = w_pax + w_frt
                    emit(region, block, "fuel_liquid", pax_c, w_pax / tot_w,
                         "4-tonne-km-equivalent",
                         "fuel follows physical work: passengers at 100 kg "
                         "(ICAO/GLEC mass allocation), freight at its tonnes")
                    emit(region, block, "fuel_liquid", frt_c, w_frt / tot_w,
                         "4-tonne-km-equivalent",
                         "fuel follows physical work: passengers at 100 kg "
                         "(ICAO/GLEC mass allocation), freight at its tonnes")
                else:
                    for c, v in sh.items():
                        emit(region, block, "fuel_liquid", c, v, "5-money",
                             "no physical work observed for either child: fuel "
                             "falls back to the monetary shares (declared)")

            # -- Q re-denomination targets --
            for c in children:
                if c == "PIPE":
                    continue
                q, src = volume.get((region, block, c), (0.0, ""))
                if q > 0:
                    unit = ("Mtkm" if c in ("ROAD.FRT", "TRN.F", "SEA", "IWW",
                                            "AIR.FRT") else "Mpkm")
                    emit(region, block, "Q", c, q, "observed",
                         f"{src} Y11, {unit}; child re-denominates to it")
                else:
                    emit(region, block, "Q", c, 0.0, "none",
                         "no observed volume: child stays MEUR (declared)")

    out = HERE / "data" / "moveb_split_spec.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "block", "row_class", "child",
                                          "share", "tier", "provenance"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"{len(rows_out)} righe spec, {len(EXIOBASE_REGIONS)} regioni -> {out}")
    print("tier 'other' per blocco:", dict(sorted(tier_count.items())))
    for region in ("IT", "US", "CN", "WA", "TW"):
        sel = [r for r in rows_out if r["region"] == region and r["row_class"] == "other"]
        line = "  ".join(f"{r['block']}/{r['child']}={r['share']}({r['tier'][0]})" for r in sel)
        print(f"  {region}: {line}")


if __name__ == "__main__":
    main()
