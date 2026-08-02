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
# SIEC products that make up road motor fuel, and their table counterparts
FUELS = {"Motor Gasoline": "Motor gasoline", "Gas/Diesel Oil": "Gas oil/diesel oil",
         "Biogasoline": "Biogasoline", "Biodiesels": "Biodiesel"}
COUNTRIES = ("IT", "DE", "FR", "ES", "PL", "US")


def unsd_road_fuel(api: str, year: int) -> pd.DataFrame:
    """Observed road fuel (t) per country, UNSD transaction 1221."""
    q = urllib.parse.urlencode({"parameter": "Use", "source": "UNSD.USE",
                                "limit": "400000"})
    raw = urllib.request.urlopen(f"{api}/data.csv?{q}", timeout=600).read().decode()  # noqa: S310
    df = pd.read_csv(io.StringIO(raw))
    df = df[(df["i2_name"].astype(str).str.contains("Road", case=False, na=False))
            & (df["i2_attr_2_name"] == year)
            & (df["i1_name"].isin(FUELS))]
    return df.groupby("i2_attr_1_name")["value"].sum()


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
    fuels = [f for f in FUELS if f in set(U.index.get_level_values(2))]
    acts = [a for a in ROAD_ACTS if a in set(U.columns.get_level_values(2))]
    print(f"combustibili trovati: {fuels}\nattivita' stradali: {len(acts)}/{len(ROAD_ACTS)}",
          flush=True)

    obs = unsd_road_fuel(api, year)
    print(f"\n{'paese':6}{'tavola (Mt)':>14}{'UNSD 1221 (Mt)':>17}{'rapporto':>11}",
          flush=True)
    for c in COUNTRIES:
        # every origin: an energy balance counts the fuel burned in the
        # country whoever refined it, so imported fuel counts too
        rows = U.loc[(slice(None), "Commodity", fuels), (c, "Activity", acts)]
        tab = float(rows.to_numpy().sum()) / 1e6
        o = float(obs.get(c, float("nan"))) / 1e6
        ratio = tab / o if o else float("nan")
        flag = "OK " if 0.6 <= ratio <= 1.15 else "!! "
        print(f"{flag}{c:4}{tab:>13,.1f}{o:>17,.1f}{ratio:>11.2f}", flush=True)
    print("\natteso: rapporto <= 1 (la tavola non deve superare l'osservato) e non "
          "troppo sotto (sarebbe carburante stradale rimasto nelle colonne industriali)",
          flush=True)


if __name__ == "__main__":
    main()
