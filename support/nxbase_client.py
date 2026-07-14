"""Query-API client for nxbase — the pipeline's only data doorway.

nxbase exposes its PostgreSQL content through a query API (`/data`,
`/data.csv`, `/sets/*`); this module wraps the calls db_gen.ipynb needs and
reshapes the rows into the exact structures MARIO consumes. The translation
logic lives here (the consumer), the base is always the API — see
nxbase docs/knowledge/nxsut_bridge.md, decision 2026-07-13.

Local dev: `uv run nxbase api` in the nxbase checkout (Docker Postgres up).
Phase 2: point `api_url` at the hosted instance — nothing else changes.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

DEFAULT_API = "http://127.0.0.1:8000"

# EMBER covers 2000+; nxbase periods are Y<yy> shorts.
_CENTURY = 2000
# User-assigned ISO codes country_converter may not resolve.
_ISO2_TO_ISO3_OVERRIDES = {"XK": "XKX"}  # Kosovo


def _get_json(api_url: str, path: str) -> object:
    with urlopen(f"{api_url.rstrip('/')}{path}") as resp:  # noqa: S310 (trusted host)
        return json.load(resp)


def _get_csv(api_url: str, params: dict[str, object]) -> pd.DataFrame:
    query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
    return pd.read_csv(f"{api_url.rstrip('/')}/data.csv?{query}")


def split_item(item: str) -> list[str]:
    """`a_coal-EXX-IT-Y24` -> ['coal', 'EXX', 'IT', 'Y24'].

    Shorts contain neither `_` nor `-` by nxbase convention, so the first
    `_` separates the type letter and `-` separates the attributes.
    """
    return item.split("_", 1)[1].split("-")


def _iso2_to_iso3(codes: pd.Series) -> pd.Series:
    import country_converter as coco

    unique = sorted(set(codes) - set(_ISO2_TO_ISO3_OVERRIDES))
    converted = coco.convert(names=unique, src="ISO2", to="ISO3", not_found=None)
    if isinstance(converted, str):  # coco returns a scalar for a single name
        converted = [converted]
    mapping = dict(zip(unique, converted)) | _ISO2_TO_ISO3_OVERRIDES
    return codes.map(mapping)


def get_provenance(api_url: str = DEFAULT_API, source_names: list[str] | None = None) -> str:
    """One-line-per-fact provenance stamp to print in the notebook run."""
    health = _get_json(api_url, "/health")
    lines = [f"nxbase version: {health['version']} (api: {api_url})"]
    if source_names:
        rows = _get_json(api_url, "/sets/source")
        for row in rows:
            if row.get("name") in source_names:
                lines.append(
                    f"source: {row.get('extended')} "
                    f"(version {row.get('version')}, status {row.get('status')})"
                )
    return "\n".join(lines)


def get_ember_snapshot(
    api_url: str = DEFAULT_API,
    source: str = "EMBER Yearly Electricity Data (generation) 2025",
) -> pd.DataFrame:
    """Electricity generation snapshot in MARIO's reduced EMBER format.

    Queries `/data.csv?parameter=Total output&source=...` and returns the
    4-column frame `update_supply_mix(ember_path=...)` reads natively
    (write it to a transient CSV): ISO3, Year, Variable, Value (TWh).
    """
    frame = _get_csv(api_url, {"parameter": "Total output", "source": source, "sort": "id"})
    if frame.empty:
        raise ValueError(f"no Total output rows for source {source!r}")

    parts = frame["item_1"].map(split_item)
    tech_short = parts.str[0]
    iso2 = parts.str[2]
    year = parts.str[3].str[1:].astype(int) + _CENTURY

    # exact EMBER labels live in the EMBER-classified activity rows
    activities = _get_json(api_url, "/sets/activity")
    label_by_short = {
        r["short"]: r["name"] for r in activities if r.get("classification") == "EMBER"
    }

    out = pd.DataFrame(
        {
            "ISO3": _iso2_to_iso3(iso2),
            "Year": year,
            "Variable": tech_short.map(label_by_short),
            "Value": frame["value"].astype(float),
        }
    )
    dropped = out["ISO3"].isna() | out["Variable"].isna()
    if dropped.any():
        print(f"nxbase_client: dropped {int(dropped.sum())} unmappable rows")
    out = out.loc[~dropped]

    # nxbase stores no zero rows (skip-zeros policy): rebuild the full
    # (country, year) x fuel grid so MARIO sees explicit zero shares.
    grid = (
        out.pivot_table(index=["ISO3", "Year"], columns="Variable", values="Value")
        .reindex(columns=sorted(label_by_short.values()))
        .fillna(0.0)
        .stack()
        .rename("Value")
        .reset_index()
    )
    return grid


def get_trade_matrix(
    api_url: str = DEFAULT_API,
    year: int = 2024,
    commodity: str = "Electricity",
) -> pd.DataFrame:
    """Origins x destinations share matrix for one commodity and year.

    Queries `/data.csv?parameter=Import mix&period=<year>&commodity=...` and
    pivots to the matrix `update_trade_mix` consumes (region shorts on both
    axes, every destination column summing to 1, domestic diagonal included).
    """
    frame = _get_csv(
        api_url,
        {
            "parameter": "Import mix",
            "period": str(year),
            "commodity": commodity,
            "sort": "id",
        },
    )
    if frame.empty:
        raise ValueError(f"no Import mix rows for {commodity!r} in {year}")

    destination = frame["item_1"].map(lambda s: split_item(s)[1])
    origin = frame["item_2"].map(lambda s: split_item(s)[0])
    matrix = pd.DataFrame(
        {"origin": origin, "destination": destination, "value": frame["value"].astype(float)}
    ).pivot(index="origin", columns="destination", values="value")
    # nxbase stores no zero rows (skip-zeros policy): re-materialize them so
    # every destination column carries the full origin universe (a missing
    # origin must force a zero share in update_trade_mix, not subset-rescale).
    universe = sorted(set(matrix.index) | set(matrix.columns))
    matrix = matrix.reindex(index=universe, columns=universe).fillna(0.0)
    matrix.index.name = None
    matrix.columns.name = None
    return matrix
