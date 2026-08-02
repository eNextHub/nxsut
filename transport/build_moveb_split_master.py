"""Move B (b) — the non-SBS split master (hand-curated tier, per-cell provenance).

For countries outside Eurostat SBS the Move-B monetary split key comes from
this assembled master (the Ghezzi pattern). Tiers per cell, declared:

- **tier 2 — SDBS observed**: KOR turnover by ISIC class from OECD SDBS
  (``DSD_SDBSBSC_ISIC4@DF_SDBS_ISIC4``, measure TUTT; national currency —
  irrelevant, only within-block shares are used). TUR turned out to be
  tier 1 (Eurostat SBS covers candidate countries; its SDBS 4-digit is
  empty anyway). The raw KOR slice is cached next to the master.
- **tier 4 — EU-median price x local volumes**: US, CN, JP and every other
  ITF-covered non-SBS country: share_child ∝ p_child x Q_child, where
  p_child = the **median in-band implicit price from diagnostic (a)**
  (moveb_implicit_prices.csv — our own observed EU prices, no literature)
  and Q_child = the country's ITF volume (2011).
- **tier 5 — SBS-median shares**: computed here from the governed
  ``ESTAT.SBSH49`` rows (Y11, per-country shares -> median): used (i) as
  the whole-block fallback when no volume exists, (ii) for any child
  whose volume is missing (ITF absence = not reported, NEVER a zero
  share), (iii) always for PIPE (no honest volume — the (a) perimeter
  finding). Renormalisation keeps each block summing to 1.
- **upgrade path** (flagged per cell, not filled): US -> BEA
  GDP-by-industry gross output (truck 484 / transit 485 / pipeline 486
  are native industries; API key needed); CN -> NBS yearbook transport
  revenue by mode; JP -> MLIT annual survey. Manual lookups — never
  invented here.

Blocks (the two base-table columns to split):

- ``road_pipe`` ("Other land transport"): ROAD.FRT / ROAD.PAX / PIPE
- ``rail``: TRN.P / TRN.F

Output: ``transport/moveb_split_master.csv``
(country, block, child, share, tier, provenance).
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

OECD = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_SDBSBSC_ISIC4@DF_SDBS_ISIC4,1.0"

BLOCKS = {"road_pipe": ["ROAD.FRT", "ROAD.PAX", "PIPE"], "rail": ["TRN.P", "TRN.F"]}
# NACE backbone shorts (as imported by ESTAT.SBSH49) -> (block, child)
SBS_MAP = {
    "H.49.41": ("road_pipe", "ROAD.FRT"), "H.49.42": ("road_pipe", "ROAD.FRT"),
    "H.49.31": ("road_pipe", "ROAD.PAX"), "H.49.33": ("road_pipe", "ROAD.PAX"),
    "H.49.39": ("road_pipe", "ROAD.PAX"), "H.49.50": ("road_pipe", "PIPE"),
    "H.49.1": ("rail", "TRN.P"), "H.49.20": ("rail", "TRN.F"),
}
# OECD SDBS ISIC classes -> (block, child)
SDBS_MAP = {
    "H4911": ("rail", "TRN.P"), "H4912": ("rail", "TRN.F"),
    "H4921": ("road_pipe", "ROAD.PAX"), "H4922": ("road_pipe", "ROAD.PAX"),
    "H4923": ("road_pipe", "ROAD.FRT"), "H4930": ("road_pipe", "PIPE"),
}
# diagnostic-(a) child -> (block, child); PIPE deliberately absent (tier 5)
PRICE_MAP = {"HGV": ("road_pipe", "ROAD.FRT"), "BUS": ("road_pipe", "ROAD.PAX"),
             "TRN.P": ("rail", "TRN.P"), "TRN.F": ("rail", "TRN.F")}
ITF_VOLUMES = {
    "Road freight transport (total)": ("road_pipe", "ROAD.FRT"),
    "Road passenger transport - buses and coaches": ("road_pipe", "ROAD.PAX"),
    "Rail passenger transport": ("rail", "TRN.P"),
    "Rail freight transport": ("rail", "TRN.F"),
}
TIER4_COUNTRIES = ["US", "CN", "JP", "KR", "IN", "AU", "CA", "RU", "BR", "MX",
                   "GE", "AM", "AZ", "MD", "UA"]
UPGRADE = {"US": "upgrade: BEA GDP-by-industry gross output (482/484/485/486, native split)",
           "CN": "upgrade: NBS yearbook transport revenue by mode",
           "JP": "upgrade: MLIT annual transport survey"}
# pipeline-heavy economies: the SBS-median PIPE share (~0, the EU median) is
# certainly wrong for them — the cell carries an explicit warning.
PIPE_HEAVY = {"US", "CN", "RU", "CA", "KZ"}


def fetch_csv(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "nxbase-pull/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def fetch_api(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def main() -> None:
    # --- tier-5 vector: SBS-median shares per block (from the governed rows) ---
    sbs: dict[tuple[str, str, str], float] = defaultdict(float)  # (iso2, block, child)
    for r in fetch_api({"parameter": "Total output",
                        "source": "Eurostat SBS transport turnover (H49-H51)",
                        "limit": "100000"}):
        parts = r["item_1"].split("-")           # a_<nace>-EXX-<iso2>-<Yxx>
        if len(parts) == 4 and parts[3] == "Y11" and parts[0][2:] in SBS_MAP:
            block, child = SBS_MAP[parts[0][2:]]
            sbs[(parts[2], block, child)] += float(r["value"])
    # Median only over countries where the CORE children are all reported:
    # an absent SBS cell is confidential-or-missing, not zero — a country
    # reporting freight but not (confidential) rail pax would contribute a
    # fake pax=0 and skew the median. PIPE may be absent (= no pipelines,
    # counts as 0): it is not a core child.
    CORE = {"road_pipe": ["ROAD.FRT", "ROAD.PAX"], "rail": ["TRN.P", "TRN.F"]}
    shares5: dict[tuple[str, str], float] = {}
    for block, children in BLOCKS.items():
        per_child: dict[str, list[float]] = defaultdict(list)
        for iso2 in {s for (s, b, _) in sbs if b == block}:
            if not all((iso2, block, c) in sbs for c in CORE[block]):
                continue
            tot = sum(sbs.get((iso2, block, c), 0.0) for c in children)
            if tot > 0:
                for c in children:
                    per_child[c].append(sbs.get((iso2, block, c), 0.0) / tot)
        med = {c: statistics.median(v) for c, v in per_child.items()}
        norm = sum(med.values())
        for c, v in med.items():
            shares5[(block, c)] = v / norm
    print("tier-5 (mediane SBS Y11):",
          {f"{b}/{c}": round(v, 3) for (b, c), v in shares5.items()})

    # --- (a) median in-band prices ---
    by_child: dict[tuple[str, str], list[float]] = defaultdict(list)
    with open(HERE / "data" / "moveb_implicit_prices.csv") as f:
        for r in csv.DictReader(f):
            if r["verdict"] == "ok" and r["year"] == "Y11" and r["child"] in PRICE_MAP:
                by_child[PRICE_MAP[r["child"]]].append(float(r["price"]))
    prices = {k: statistics.median(v) for k, v in by_child.items()}
    print("mediane prezzi in-band Y11 (EUR/unit):",
          {f"{b}/{c}": round(p, 3) for (b, c), p in prices.items()})

    # --- ITF volumes (Y11) for tier-4 countries ---
    volume: dict[tuple[str, str, str], float] = defaultdict(float)
    for r in fetch_api({"parameter": "Total output",
                        "source": "International Transport Forum", "limit": "200000"}):
        if r["i1_name"] in ITF_VOLUMES:
            parts = r["item_1"].split("-")
            if len(parts) == 4 and parts[2] in TIER4_COUNTRIES and parts[3] == "Y11":
                block, child = ITF_VOLUMES[r["i1_name"]]
                volume[(parts[2], block, child)] += float(r["value"])

    rows_out: list[dict] = []
    done: set[tuple[str, str]] = set()          # (country, block) already emitted

    # --- tier 2: SDBS observed (KOR road block) ---
    kor = fetch_csv(f"{OECD}/A.KOR....?startPeriod=2011&endPeriod=2011&format=csvfile")
    with open(HERE / "data" / "sdbs_h49_kor_2011.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(kor[0].keys()))
        w.writeheader()
        w.writerows([r for r in kor if r["ACTIVITY"].startswith("H49")])
    vals: dict[tuple[str, str], float] = defaultdict(float)
    for r in kor:
        if r["MEASURE"] == "TUTT" and r["ACTIVITY"] in SDBS_MAP and r["OBS_VALUE"]:
            vals[SDBS_MAP[r["ACTIVITY"]]] += float(r["OBS_VALUE"])
    for block, children in BLOCKS.items():
        obs = {c: vals[(b, c)] for (b, c) in vals if b == block}
        if not obs:
            continue
        missing = [c for c in children if c not in obs]
        fixed = {c: shares5[(block, c)] for c in missing}
        rest = 1 - sum(fixed.values())
        tot = sum(obs.values())
        for c, v in sorted(obs.items()):
            rows_out.append(dict(country="KR", block=block, child=c,
                                 share=round(rest * v / tot, 4), tier="2-SDBS",
                                 provenance="OECD SDBS ISIC4 TUTT 2011, shares within "
                                 "block; missing children filled with SBS-median"))
        for c, v in fixed.items():
            rows_out.append(dict(country="KR", block=block, child=c,
                                 share=round(v, 4), tier="5-median",
                                 provenance="SBS Y11 EU-median share (no SDBS/volume cell)"))
        done.add(("KR", block))

    # --- tier 4 / 5 ---
    for iso2 in TIER4_COUNTRIES:
        for block, children in BLOCKS.items():
            if (iso2, block) in done:
                continue
            present = {c: volume.get((iso2, block, c), 0.0) for c in children
                       if (block, c) in prices and volume.get((iso2, block, c), 0.0) > 0}
            fixed = {c: shares5[(block, c)] for c in children if c not in present}
            if not present:
                if not any(volume.get((iso2, b, c), 0) > 0
                           for b in BLOCKS for c in BLOCKS[b]):
                    continue                     # nothing observed at all -> builder tier 5
                for c, v in fixed.items():
                    rows_out.append(dict(country=iso2, block=block, child=c,
                                         share=round(v, 4), tier="5-median",
                                         provenance="SBS Y11 EU-median share "
                                         "(no volume observed for this block)"))
                continue
            rest = 1 - sum(fixed.values())
            weights = {c: prices[(block, c)] * q for c, q in present.items()}
            tot = sum(weights.values())
            prov = ("tier 4: EU-median in-band implicit price (diagnostic a) x ITF "
                    "Y11 volumes. " + UPGRADE.get(iso2, "")).strip()
            for c, wgt in sorted(weights.items()):
                rows_out.append(dict(country=iso2, block=block, child=c,
                                     share=round(rest * wgt / tot, 4),
                                     tier="4-price-x-volume", provenance=prov))
            for c, v in sorted(fixed.items()):
                note = ("SBS Y11 EU-median share (volume not reported to ITF — "
                        "never a silent zero)")
                if c == "PIPE" and iso2 in PIPE_HEAVY:
                    note += ("; WARNING pipeline-heavy economy, EU-median ~0 is "
                             "certainly low — upgrade cell first")
                rows_out.append(dict(country=iso2, block=block, child=c,
                                     share=round(v, 4), tier="5-median",
                                     provenance=note))

    out = HERE / "data" / "moveb_split_master.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["country", "block", "child", "share",
                                          "tier", "provenance"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"\n{len(rows_out)} celle, {len({r['country'] for r in rows_out})} paesi -> {out}")
    for c in ("KR", "US", "CN", "JP", "IN", "RU"):
        sel = [r for r in rows_out if r["country"] == c]
        line = "  ".join(f"{r['block']}/{r['child']}={r['share']}({r['tier'][0]})"
                         for r in sel)
        print(f"  {c}: {line}")


if __name__ == "__main__":
    main()
