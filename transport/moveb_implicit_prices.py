"""Move B (a) — implicit unit revenues: is the re-denomination clean?

For each Move-B child, the split key (SBS turnover, MEUR) divided by the
observed service volume (pkm/tkm) gives the **implicit unit revenue** —
EUR/tkm for freight, EUR/pkm for passenger (MEUR ÷ M[pt]km = EUR per unit,
no scaling). Known bands exist, so every (country, child) gets a
plausibility verdict *before* the split is built: in-band = the
re-denomination is clean; out-of-band = perimeter mismatch radar
(enterprise residence vs territory, subsidy share, coverage holes).

All inputs come from the nxbase query API (both sides governed):
``ESTAT.SBSH49`` turnover vs ITF/ESTAT volumes (ESTAT preferred, ITF
fallback — declared per row).

Perimeter notes (declared):

- SBS is enterprise-based by main activity → freight turnover matches the
  **hire-and-reward** tkm perimeter (not total road tkm): the comparison
  uses ``frt.hire``;
- bus/rail turnover excludes operating subsidies → the implicit number is
  *revenue* per pkm, expected below full cost for public transport (bands
  set accordingly);
- volumes are territory-based, turnover residence-based — international
  hauliers (LT, PL, NL…) can sit above band by construction: that is the
  radar working, not noise.

Output: ``transport/moveb_implicit_prices.csv`` + a printed verdict table.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "http://127.0.0.1:8000"
SBS_SOURCE = "Eurostat SBS land-transport turnover (H49)"

# child -> (SBS NACE shorts summed, volume specs [(source, activity, unit)...
#           first hit wins], unit label, plausibility band EUR/unit)
CHILDREN: dict[str, dict] = {
    "HGV": {
        "sbs": ["H.49.41", "H.49.42"],
        "volumes": [("Eurostat road freight by operation (tkm)",
                     "Road freight transport - hire and reward"),
                    ("International Transport Forum",
                     "Road freight transport - hire and reward")],
        "unit": "EUR/tkm", "band": (0.08, 0.45),
    },
    "BUS": {
        "sbs": ["H.49.31", "H.49.33", "H.49.39"],
        "volumes": [("Eurostat road passenger performance (pkm)",
                     "Road passenger transport - buses, coaches and trolleys"),
                    ("International Transport Forum",
                     "Road passenger transport - buses and coaches")],
        "unit": "EUR/pkm", "band": (0.03, 0.40),
    },
    "TRN.P": {
        "sbs": ["H.49.1"],
        "volumes": [("Eurostat rail passenger transport (pkm)", "Rail passenger transport"),
                    ("International Transport Forum", "Rail passenger transport")],
        "unit": "EUR/pkm", "band": (0.02, 0.25),
    },
    "TRN.F": {
        "sbs": ["H.49.20"],
        "volumes": [("International Transport Forum", "Rail freight transport")],
        "unit": "EUR/tkm", "band": (0.01, 0.12),
    },
    "PIPE": {
        "sbs": ["H.49.50"],
        "volumes": [("International Transport Forum", "Pipeline freight transport")],
        "unit": "EUR/tkm", "band": (0.003, 0.10),
    },
}
YEARS = ("Y11", "Y19")   # the base-table year + a recent stability check


def fetch(params: dict) -> list[dict]:
    url = f"{API}/data.csv?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
        return list(csv.DictReader(io.StringIO(r.read().decode())))


def main() -> None:
    # SBS turnover: (nace_short, iso2, year) -> MEUR
    turnover: dict[tuple[str, str, str], float] = defaultdict(float)
    for r in fetch({"parameter": "Total output", "source": SBS_SOURCE, "limit": "100000"}):
        parts = r["item_1"].split("-")          # a_<nace>-EXX-<iso2>-<Yxx>
        if len(parts) == 4 and parts[3] in YEARS:
            turnover[(parts[0][2:], parts[2], parts[3])] += float(r["value"])

    # volumes: (source_name, activity_name, iso2, year) -> M[pt]km
    volume: dict[tuple[str, str, str, str], float] = defaultdict(float)
    wanted = {(src, act) for c in CHILDREN.values() for src, act in c["volumes"]}
    for src in sorted({s for s, _ in wanted}):
        for r in fetch({"parameter": "Total output", "source": src, "limit": "200000"}):
            parts = r["item_1"].split("-")
            if len(parts) == 4 and parts[3] in YEARS:
                volume[(src, r["i1_name"], parts[2], parts[3])] += float(r["value"])

    rows_out: list[dict] = []
    for child, spec in CHILDREN.items():
        lo, hi = spec["band"]
        sites = sorted({s for (n, s, _) in turnover if n in spec["sbs"]})
        for site in sites:
            for yr in YEARS:
                t = sum(turnover.get((n, site, yr), 0.0) for n in spec["sbs"])
                q, q_src = 0.0, ""
                for src, act in spec["volumes"]:
                    q = volume.get((src, act, site, yr), 0.0)
                    if q > 0:
                        q_src = "ESTAT" if "Eurostat" in src else "ITF"
                        break
                if t <= 0 or q <= 0:
                    continue
                price = t / q                    # MEUR / M[pt]km = EUR per unit
                rows_out.append({
                    "child": child, "site": site, "year": yr,
                    "turnover_MEUR": round(t, 1), "volume_M": round(q, 1),
                    "vol_source": q_src, "price": round(price, 4),
                    "unit": spec["unit"],
                    "verdict": "ok" if lo <= price <= hi else
                               ("HIGH" if price > hi else "LOW"),
                })

    out = Path(__file__).parent / "moveb_implicit_prices.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    n_ok = sum(1 for r in rows_out if r["verdict"] == "ok")
    print(f"{len(rows_out)} (child x paese x anno) -> {out}   in banda: {n_ok} "
          f"({100 * n_ok // len(rows_out)}%)\n")
    print("Y11 (l'anno dello split) — paesi chiave:")
    for child in CHILDREN:
        sel = [r for r in rows_out if r["child"] == child and r["year"] == "Y11"
               and r["site"] in ("IT", "DE", "FR", "ES", "PL", "NL", "LT", "SE", "AT")]
        line = "  ".join(f"{r['site']}={r['price']:.3f}{'!' if r['verdict'] != 'ok' else ''}"
                         for r in sorted(sel, key=lambda x: x["site"]))
        print(f"  {child:6} [{CHILDREN[child]['unit']}]  {line}")
    print("\nfuori banda Y11 (radar):")
    for r in rows_out:
        if r["year"] == "Y11" and r["verdict"] != "ok":
            print(f"  {r['child']:6} {r['site']:3} {r['price']:.3f} {r['unit']} "
                  f"({r['verdict']}, vol {r['vol_source']})")


if __name__ == "__main__":
    main()
