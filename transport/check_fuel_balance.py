"""Does the transport layer's road fuel match the observed energy balance?

The whole point of Move C (own-account externalisation) is that the SUT's
transport perimeter should line up with UNSD's: IRES transaction **1221 =
road** is *all* road fuel, whoever burns it — hauliers, bus operators,
households and the manufacturer running its own lorries. In the table that
is the motor gasoline + diesel bought by the road transport family:

    hire-and-reward freight + own-account freight + road passenger
    + the private car activities (Move A) + motorcycles

Anything left in the industry columns is process heat, off-road machinery
and heating, which 1221 excludes — so the table total should come in at or
slightly below the observed one, never above it.

    unset VIRTUAL_ENV; /opt/anaconda3/envs/mario/bin/python \\
        transport/check_fuel_balance.py [year] [version]
"""

from __future__ import annotations

import io
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROAD_ACTS = [
    "Road freight transport", "Own-account road freight transport",
    "Road passenger transport", "Private car transport, gasoline",
    "Private car transport, diesel", "Private car transport, LPG",
    "Private car transport, natural gas", "Private motorcycle transport",
]
# Liquid motor fuel only, on both sides. LPG and CNG road use exists but is
# a couple of per cent and its table counterpart is a distributed-gas
# commodity that also serves heating, so it would compare two different
# things; electricity likewise. SIEC names carry their code.
TABLE_FUELS = ["Motor Gasoline", "Gas/Diesel Oil", "Biogasoline", "Biodiesels"]
SIEC_FUELS = ["4652 Motor Gasoline", "4670 Gas Oil/ Diesel Oil",
              "5210 Biogasoline", "5220 Biodiesel"]   # never the "Of which:" rows
UNSD_SOURCE = "UNSD Energy Statistics — fuel use by sector 2021-2023"
COUNTRIES = ("IT", "DE", "FR", "ES", "PL", "US", "CN", "JP")


def unsd_road_fuel(api: str, year: int) -> pd.Series:
    """Observed road fuel (t) per country: UNSD/IRES transaction 1221."""
    q = urllib.parse.urlencode({"source": UNSD_SOURCE,
                                "activity": "Consumption by road", "limit": "400000"})
    raw = urllib.request.urlopen(f"{api}/data.csv?{q}", timeout=900).read().decode()  # noqa: S310
    df = pd.read_csv(io.StringIO(raw))
    df = df[df["i1_name"].isin(SIEC_FUELS)].copy()
    # item_2 is 'a_1221-<site>-<period>' — the attribute *names* are extended
    # ("Italy"), so the codes come from the item string
    parts = df["item_2"].astype(str).str.split("-")
    df["site"] = parts.str[1]
    df["period"] = parts.str[2]
    df = df[df["period"] == f"Y{year % 100:02d}"]
    return df.groupby("site")["value"].sum()


def main() -> None:
    import mario

    year = int(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NXSUT_YEAR", 2023))
    version = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NXSUT_VERSION", "v3.2")
    pfile = ROOT / ("paths_personal.yml" if (ROOT / "paths_personal.yml").exists()
                    else "paths.yml")
    paths = yaml.safe_load(open(pfile))["USER"]
    api = paths.get("nxbase_api", "http://127.0.0.1:8000")

    db = mario.parse_from_txt(os.path.join(paths["export"], version, str(year), "flows"),
                              table="SUT", mode="flows")
    U = db.U
    fuels = [f for f in TABLE_FUELS if f in set(U.index.get_level_values(2))]
    acts = [a for a in ROAD_ACTS if a in set(U.columns.get_level_values(2))]
    print(f"combustibili trovati: {fuels}\nattivita' stradali: {len(acts)}/{len(ROAD_ACTS)}",
          flush=True)

    obs = unsd_road_fuel(api, year)
    Y = db.Y
    # Move A moves household motor fuel into the car activities only up to the
    # bottom-up transport demand (vehicle-km x intensity); whatever a
    # household bought beyond that stays in final demand. It is still road
    # fuel as far as transaction 1221 is concerned, so the comparison is a
    # BRACKET: activities alone are the lower bound, activities plus all the
    # household motor fuel left in Y the upper one (the upper bound leaks a
    # little heating oil, since Gas/Diesel Oil serves both).
    hh = [col for col in Y.columns
          if "households" in str(col[2]) or "non-profit" in str(col[2])]
    print(f"\n{'paese':6}{'attivita (Mt)':>15}{'+ famiglie':>13}"
          f"{'UNSD 1221':>12}{'rapporto':>20}", flush=True)
    for c in COUNTRIES:
        # every origin: an energy balance counts the fuel burned in the
        # country whoever refined it, so imported fuel counts too
        rows = U.loc[(slice(None), "Commodity", fuels), (c, "Activity", acts)]
        low = float(rows.to_numpy().sum()) / 1e6
        hh_c = [col for col in hh if col[0] == c]
        resid = float(Y.loc[(slice(None), "Commodity", fuels), hh_c].to_numpy().sum()) / 1e6
        high = low + resid
        o = float(obs.get(c, float("nan"))) / 1e6
        r_lo, r_hi = (low / o, high / o) if o else (float("nan"),) * 2
        flag = "OK " if r_lo <= 1.2 and r_hi >= 0.7 else "!! "
        print(f"{flag}{c:4}{low:>14,.1f}{high:>13,.1f}{o:>12,.1f}"
              f"{r_lo:>11.2f} - {r_hi:.2f}", flush=True)
    print("\nLettura. Il test e' di PERIMETRO, non di livello: la tavola porta i "
          "volumi fisici dell'anno base EXIOBASE (2011) — il '2023' riguarda i mix "
          "elettrici e di trade — mentre l'osservato e' 2021-23, quindi un divario "
          "di vintage e' atteso (crescita fuori UE, calo in UE).", flush=True)
    print("L'osservato dovrebbe cadere DENTRO l'intervallo, o poco sotto il suo "
          "estremo superiore. Sotto l'estremo inferiore vorrebbe dire carburante "
          "stradale rimasto nelle colonne industriali (Move C non ha estratto "
          "abbastanza); sopra l'estremo superiore, che la tavola ha preso anche "
          "combustibile che 1221 esclude (calore di processo, macchine off-road).",
          flush=True)


if __name__ == "__main__":
    main()
