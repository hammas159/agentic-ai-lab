"""graph-clinic agents: ingestion, entity linking, traversal, synthesis.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Edge, reachable, shortest
from .hotpot import load as _hotpot
from .hotpot import mentions as _mentions


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("ingester", "document.*", Level.WRITE)
        .grant("entity-linker", "mention.*", Level.WRITE)
        .grant("graph-builder", "edge.*", Level.WRITE)
        .grant("graph-builder", "edge.inferred", Level.NEVER)
        .grant("synthesiser", "answer.draft", Level.WRITE)
    )


def _graph(state: dict) -> tuple[list, str, str]:
    """The edges to walk, and the pair to connect.

    Supplied directly by the unit tests. Otherwise built from a real HotpotQA
    item: paragraph titles are entities and a title mentioned in another
    paragraph's text is an edge, with that paragraph as the source.
    """
    if state.get("edges") is not None:
        return (
            [Edge(e["src"], e["rel"], e["dst"], e["source"]) for e in state["edges"]],
            state.get("start", ""),
            state.get("end", ""),
        )
    items = _hotpot(state.get("limit", 200))
    wanted = state.get("item_id")
    item = next(
        (i for i in items if wanted in (None, i.id) and i.gold_present and len(i.gold) > 1),
        None,
    )
    if item is None:
        return [], "", ""
    edges = [Edge(src, "mentions", dst, src) for src, dst in sorted(_mentions(item))]
    return edges, item.gold[0], item.gold[1]


def triage(state: dict) -> dict:
    """A bounded walk that carries the document behind every hop."""
    edges, start, end = _graph(state)
    path = shortest(edges, start, end) if end else None
    return {
        "reachable": sorted(reachable(edges, start, state.get("max_hops", 2))),
        "path": list(path.nodes) if path else [],
        "path_sources": list(path.sources) if path else [],
        "summary_subject": list(path.sources) if path else [],
    }


def early_exit(state: dict) -> bool:
    """No evidenced path. Returning nothing beats returning a fluent guess."""
    return not state.get("path")


def on_exit(state: dict) -> dict:
    return {"no_path": True, "reason": "no evidenced connection between those entities"}


def commit(state: dict) -> dict:
    return {"answer.draft": state.get("draft", ""), "cites": state.get("path_sources", [])}


def _edges(state: dict) -> list[str]:
    """The mention edges available, as receipts."""
    edges, _, _ = _graph(state)
    return sorted({f"{e.src}->{e.dst}" for e in edges})[:40]


def _paths(state: dict) -> list[str]:
    """The documents the path crossed. The citation list."""
    return sorted(state.get("path_sources", []))


def default_sources() -> dict:
    """Both branches read the real HotpotQA item."""
    return {"edges": _edges, "paths": _paths}
