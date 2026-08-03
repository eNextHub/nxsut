"""Walk the nxbase set graph — the concordances the LP needs.

nxbase governs every source **native** and defers the mapping to the Rosetta
parent links (BACI's ``HS22 -> CN26 -> NXS`` pattern). The nowcast needs three
walks, all the same shape:

- **SIEC product -> NXS commodity** (the energy carriers): which table row does
  an energy-balance fuel land on. This also *defines* the ``fuels`` set: a
  commodity row is an endogenous carrier exactly when a balance observation
  can bind it.
- **IRES sector -> NXS activity** (``B_ires``): which columns a balance bucket
  constrains. IRES sectors anchor on NACE (directly or through the NXB
  manufacturing bridges), NXS activities anchor on NACE too, so the bucket of
  an activity is the IRES row whose anchor is its nearest NACE ancestor.
- **USGS / FAO item -> NXS commodity** (the physical output anchors), same
  walk on the commodity graph.

The rule everywhere is **most specific wins**: a leaf resolves to the anchor
whose ancestor chain it enters first. Where two source rows resolve to the
same NXS row the caller decides (sum for observations, refuse for keys).

Everything is read through the query API — the governed doorway — and cached
per process.
"""

from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import urlopen

DEFAULT_API = "http://127.0.0.1:8000"
LIMIT = 50000

# The namespaces each walk has to see: the two ends plus the official backbone
# they meet on (a SIEC product and an NXS commodity share a CN26 ancestor, an
# IRES sector and an NXS activity share a NACE one — sometimes through an NXB
# bridge). Fetching the whole table instead would be ~20k commodity rows.
BACKBONE = {
    "commodity": ("CN26", "EBOPS", "NXB"),
    "activity": ("NACE", "NXB"),
    "flow": ("NXB",),
}


@lru_cache(maxsize=None)
def _set_rows(api_url: str, table: str, classifications: tuple[str, ...]) -> tuple[dict, ...]:
    params: list[tuple[str, str | int]] = [("limit", LIMIT)]
    params += [("classification", c) for c in classifications]
    url = f"{api_url.rstrip('/')}/sets/{table}?{urlencode(params)}"
    with urlopen(url) as resp:  # noqa: S310 (trusted host)
        payload = tuple(json.load(resp))
    if len(payload) >= LIMIT:
        raise RuntimeError(f"/sets/{table} hit the {LIMIT}-row cap — narrow the namespaces")
    return payload


def rows(table: str, *classifications: str, api_url: str = DEFAULT_API) -> list[dict]:
    """Rows of one set table, restricted to the given namespaces (+ backbone).

    No namespace given = the whole table (only safe for the small ones).
    """
    wanted = tuple(sorted({*classifications, *BACKBONE.get(table, ())})) if classifications else ()
    return list(_set_rows(api_url, table, wanted))


def ancestors(extended: str, parent_of: dict[str, str | None]) -> list[str]:
    """``[self, parent, grandparent, ...]`` — the chain, self first.

    Cycles are broken defensively (the workbook has carried self-loops before).
    """
    chain: list[str] = []
    seen: set[str] = set()
    node: str | None = extended
    while node is not None and node not in seen:
        chain.append(node)
        seen.add(node)
        node = parent_of.get(node)
    return chain


def parent_map(table: str, *classifications: str, api_url: str = DEFAULT_API) -> dict[str, str | None]:
    return {r["extended"]: r["parent"] for r in rows(table, *classifications, api_url=api_url)}


def resolve(
    table: str,
    source_cls: str,
    target_cls: str,
    api_url: str = DEFAULT_API,
) -> dict[str, str]:
    """Map every ``source_cls`` row of ``table`` onto a ``target_cls`` row.

    Walks each source row's ancestor chain and returns the **most specific**
    target row found on it: the first chain node that is itself a target row,
    else the first node that some target row hangs under (deepest such target
    when several share the node — ties broken by the longer chain, i.e. the
    more specific one).

    Returns ``{source extended -> target extended}``; unresolved sources are
    simply absent (the caller reports them).
    """
    par = parent_map(table, source_cls, target_cls, api_url=api_url)
    all_rows = rows(table, source_cls, target_cls, api_url=api_url)
    targets = [r for r in all_rows if r["classification"] == target_cls]
    sources = [r for r in all_rows if r["classification"] == source_cls]

    # every target, keyed by each node of its own ancestor chain, keeping the
    # most specific target per node (the one whose chain is longest)
    by_node: dict[str, tuple[int, str]] = {}
    for t in targets:
        chain = ancestors(t["extended"], par)
        depth = len(chain)
        for node in chain:
            best = by_node.get(node)
            if best is None or depth > best[0]:
                by_node[node] = (depth, t["extended"])

    out: dict[str, str] = {}
    for s in sources:
        for node in ancestors(s["extended"], par):
            hit = by_node.get(node)
            if hit is not None:
                out[s["extended"]] = hit[1]
                break
    return out


def resolve_reverse(
    table: str,
    source_cls: str,
    target_cls: str,
    api_url: str = DEFAULT_API,
) -> dict[str, list[str]]:
    """``{target extended -> [source extended, ...]}`` — the grouped inverse."""
    grouped: dict[str, list[str]] = {}
    for src, tgt in resolve(table, source_cls, target_cls, api_url).items():
        grouped.setdefault(tgt, []).append(src)
    return grouped


def name_of(table: str, *classifications: str, api_url: str = DEFAULT_API) -> dict[str, str]:
    """``extended -> name`` (the label the exported table carries)."""
    return {r["extended"]: r["name"] for r in rows(table, *classifications, api_url=api_url)}


def short_of(table: str, *classifications: str, api_url: str = DEFAULT_API) -> dict[str, str]:
    return {r["extended"]: r["short"] for r in rows(table, *classifications, api_url=api_url)}


def by_short(table: str, cls: str, api_url: str = DEFAULT_API) -> dict[str, dict]:
    return {r["short"]: r for r in rows(table, cls, api_url=api_url) if r["classification"] == cls}
