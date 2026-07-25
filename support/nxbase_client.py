"""Query-API client for nxbase — the pipeline's only data doorway.

nxbase exposes its PostgreSQL content through a query API (`/data`,
`/data.csv`, `/sets/*`); this module wraps the calls the gen_v*.ipynb
notebooks need and reshapes the rows into the exact structures MARIO
consumes. The translation
logic lives here (the consumer), the base is always the API — see
nxbase docs/knowledge/nxsut_bridge.md, decision 2026-07-13.

Data access: the hosted nxbase API serves the open sources anonymously (no
login, no key) — set `api_url` / `paths.yml:nxbase_api` to the public instance
(`https://enextgen.it/nxbase-api`); the nxbase repository itself is private.
Run a local nxbase (`uv run nxbase api`, Docker Postgres up) only if you have
the checkout, then point `api_url` at `http://127.0.0.1:8000`.
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
    source: str | None = None,
) -> pd.DataFrame:
    """Origins x destinations share matrix for one commodity and year.

    Queries `/data.csv?parameter=Import mix&period=<year>&commodity=...` and
    pivots to the matrix `update_trade_mix` consumes (region shorts on both
    axes, every destination column summing to 1, domestic diagonal included).

    `source` pins the origin dataset by name (several import-mix sources now
    coexist in nxbase): the proprietary Electricity Maps set
    (`"Electricity Maps Import mix <year>"`, used by v2.x) or the open ENTSO-E
    physical set (`"ENTSO-E electricity import mix <year>"`, used by v3.0).
    Leave `None` only when a single source is present.
    """
    params: dict[str, object] = {
        "parameter": "Import mix",
        "period": str(year),
        "commodity": commodity,
        "sort": "id",
    }
    if source is not None:
        params["source"] = source
    frame = _get_csv(api_url, params)
    if frame.empty:
        raise ValueError(
            f"no Import mix rows for {commodity!r} in {year}"
            + (f" from source {source!r}" if source else "")
        )

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


def get_add_sectors_recipe(
    api_url: str = DEFAULT_API,
    source: str = "Ghezzi et al. 2026 - steel & H2 inventory",
) -> pd.DataFrame:
    """Fetch an add_sectors unit-process recipe from nxbase, reshaped by route.

    Queries `/data.csv?source=<name>` and returns the per-route inventory the
    pipeline reattaches to a base table (via its own clusters/placement) before
    MARIO `add_sectors`. Columns: `route` (the new activity), `input` (the
    resolved item name), `item_type` (`Commodity` | `Satellite account` |
    `Factor of production` | `output`), `quantity`, `unit`.

    nxbase holds only the *generic recipe* (quantities + backbone-anchored
    items). The *base-DB attachment* — which EXIOBASE commodity each input maps
    to (the cluster / DB Item), the GLOBAL/market-share placement, the
    furnace-gas emission reallocation — stays here in the pipeline: the recipe's
    resolved concepts (e.g. `Carbon dioxide, fossil`) are mapped back to the
    base table's labels by the caller. Round-trip verified: the reconstructed
    quantities equal the original master.
    """
    frame = _get_csv(api_url, {"source": source, "sort": "id", "limit": 100000})
    if frame.empty:
        raise ValueError(f"no add_sectors rows for source {source!r}")

    def _item_type(row: pd.Series) -> str:
        if row["parameter"] == "VA":
            return "Factor of production"
        if row["parameter"] == "SUP":
            return "output"
        if row["i1_set"] == "flow":
            return "Satellite account"
        return "Commodity"

    out = pd.DataFrame(
        {
            "route": frame["i2_name"].fillna(frame["i1_name"]).astype(str).str.strip(),
            "input": frame["i1_name"].astype(str).str.strip(),
            "item_type": frame.apply(_item_type, axis=1),
            "quantity": frame["value"].astype(float),
            "unit": frame["unit"],
        }
    )
    return out.reset_index(drop=True)


_STEEL_ROUTE_LABEL = {"BF.BOF": "BF-BOF", "DRI.EAF": "DRI-EAF", "SCRAP.EAF": "scrap-EAF"}


def get_steel_route_mix(
    api_url: str = DEFAULT_API,
    year: int = 2024,
    source: str = "World Steel in Figures - crude steel by route",
) -> dict[str, dict[str, float]]:
    """Per-region crude-steel production shares by route, for `update_supply_mix`.

    Queries `/data.csv?parameter=Supply&source=WSTEEL&period=<year>` (SUP holds
    absolute Mt by route — nxbase ingests the level, the mix is derived here) and
    returns `{ISO2 region: {route: share}}`, shares summing to 1 per region. Routes:
    `BF-BOF` (primary, blast furnace), `DRI-EAF` (primary, ore via DRI), `scrap-EAF`
    (secondary/recycled).

    For the EXIOBASE 2-way split, collapse in the notebook: primary = BF-BOF + DRI-EAF,
    secondary = scrap-EAF, mapped to the base table's steel activities (primary steel
    vs the secondary re-processing activity). Region keys are ISO2 — map to the table's
    regions (44 EXIOBASE + RoW) at the call site.
    """
    frame = _get_csv(
        api_url, {"parameter": "Supply", "source": source, "period": str(year), "sort": "id"}
    )
    if frame.empty:
        raise ValueError(f"no Supply rows for source {source!r} in {year}")
    parts = frame["item_2"].map(split_item)  # [route_short, ISO2, period]
    df = pd.DataFrame(
        {
            "region": parts.str[1],
            "route": parts.str[0].map(_STEEL_ROUTE_LABEL),
            "value": frame["value"].astype(float),
        }
    )
    mix: dict[str, dict[str, float]] = {}
    for region, g in df.groupby("region"):
        total = g["value"].sum()
        if total > 0:
            mix[region] = {r: round(v / total, 6) for r, v in zip(g["route"], g["value"])}
    return mix


def get_glass_recycled_share(
    api_url: str = DEFAULT_API,
    year: int = 2024,
    source: str = "FEVE / Close the Glass Loop - glass collection rate",
) -> dict[str, float]:
    """Per-country recycled/secondary glass share (0-1), `{ISO2: share}`.

    Queries `/data.csv?parameter=Market share&source=FEVE&period=<year>`; the value is
    the FEVE collection-for-recycling rate (a proxy for the cullet supply share). EU-only.
    Scale by the EU-average cullet content (~0.535) at the call site if you want the
    absolute secondary share; use it directly for a relative country modulation.
    """
    frame = _get_csv(
        api_url,
        {"parameter": "Market share", "source": source, "period": str(year), "sort": "id"},
    )
    if frame.empty:
        raise ValueError(f"no Market share rows for source {source!r} in {year}")
    region = frame["item_1"].map(lambda s: split_item(s)[1])  # c_GLAW-<ISO2>-<period>
    return dict(zip(region, frame["value"].astype(float)))


def get_plastics_recycled_share(
    api_url: str = DEFAULT_API,
    year: int = 2019,
    source: str = "OECD Global Plastics Outlook - world secondary share",
) -> float:
    """World secondary (recycled) plastics use share (0-1) for `year` (site LXX).

    The OECD split is world-only; apply this uniformly across regions (the per-region
    OECD-macro-region rate is a documented follow-up). OECD baseline stops at 2019.
    """
    frame = _get_csv(
        api_url,
        {"parameter": "Market share", "source": source, "period": str(year), "sort": "id"},
    )
    if frame.empty:
        raise ValueError(f"no Market share rows for source {source!r} in {year}")
    return float(frame["value"].iloc[0])


# Pipeline-side cluster: nxbase-resolved concept -> the base table's label.
_ADD_SECTORS_REVERSE_CLUSTER = {
    "Carbon dioxide, fossil": "CO2",
    "Methane, fossil": "CH4",
    "Nitrous oxide": "N2O",
    "Operating surplus: Consumption of fixed capital": "CAPEX",
    "Coke Oven Coke": "Coke",
}
# Base-table remap applied to the master's DB Item column. add_sectors runs
# AFTER aggregate_ee, where the electricity generation commodities are folded
# into a single grid "Electricity" — so the ETE master's consolidated
# "Electricity" / "Electricity RES" both point at "Electricity". (A finer
# electricity attachment is a known later refinement.)
_ADD_SECTORS_DBITEM_REMAP = {
    "Electricity": "Electricity",
    "Electricity RES": "Electricity",
}


def build_add_sectors_master(
    template_path: str,
    out_path: str,
    api_url: str = DEFAULT_API,
    source: str = "Ghezzi et al. 2026 - steel & H2 inventory",
) -> str:
    """Write an add_sectors master driven by the nxbase recipe.

    The **recipe** (per-route quantities) comes from nxbase; the **base-DB
    attachment** — the GLOBAL/market-share placement and the Regions cluster
    sheet — is kept from ``template_path`` (the original master). Two ETE-legacy
    fixes are applied for nxsut's post-``aggregate_ee`` base: the DB Item column
    remaps electricity to the single grid "Electricity", and the ETE
    "Commodities Clusters" sheet (which groups generation-split electricity
    commodities that do not exist here — and collide with the aggregated EMBER
    activity labels) is cleared. add_sectors must run AFTER aggregate_ee.
    Returns ``out_path``.
    """
    import openpyxl

    recipe = get_add_sectors_recipe(api_url, source)
    # (activity, base-table label) -> quantity from nxbase
    qty: dict[tuple[str, str], float] = {}
    for _, r in recipe[recipe["item_type"] != "output"].iterrows():
        label = _ADD_SECTORS_REVERSE_CLUSTER.get(r["input"], r["input"])
        qty[(r["route"].strip(), label.strip())] = r["quantity"]

    wb = openpyxl.load_workbook(template_path)
    # Drop the ETE electricity Commodities Clusters (Coal/Hydro/Solar... are not
    # commodities in the aggregated base, and 'Coal' collides with the EMBER
    # activity label -> copy_from_parent KeyError). Keep the header row only.
    cc = wb["Commodities Clusters"]
    if cc.max_row > 1:
        cc.delete_rows(2, cc.max_row - 1)
    ms = wb["Master"]
    mh = [c.value for c in next(ms.iter_rows(min_row=1, max_row=1))]
    mi = {h: i for i, h in enumerate(mh)}
    sheet_to_act = {
        ms.cell(row=rr, column=mi["Inventory sheet"] + 1).value: ms.cell(row=rr, column=mi["Activity"] + 1).value
        for rr in range(2, ms.max_row + 1)
        if ms.cell(row=rr, column=mi["Inventory sheet"] + 1).value
    }
    struct = {"Master", "Commodities Clusters", "Regions Clusters", "DB units"}
    for sheet in wb.sheetnames:
        if sheet in struct:
            continue
        ws = wb[sheet]
        hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        idx = {h: i for i, h in enumerate(hdr)}
        act = str(sheet_to_act.get(sheet, "")).strip()
        for rr in range(2, ws.max_row + 1):
            label = ws.cell(row=rr, column=idx["Input"] + 1).value
            if label is None:
                continue
            # remap the DB Item for nxsut's aggregated base
            dbi_cell = ws.cell(row=rr, column=idx["DB Item"] + 1)
            if dbi_cell.value in _ADD_SECTORS_DBITEM_REMAP:
                dbi_cell.value = _ADD_SECTORS_DBITEM_REMAP[dbi_cell.value]
            # overwrite quantity from nxbase where the recipe carries this input
            key = (act, str(label).strip())
            if key in qty:
                ws.cell(row=rr, column=idx["Quantity"] + 1).value = qty[key]
    wb.save(out_path)
    return out_path

