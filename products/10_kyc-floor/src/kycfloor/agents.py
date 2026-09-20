"""kyc-floor agents: document verification, screening, alert triage.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import screen
from .ofac import individuals


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("doc-verifier", "identity.*", Level.WRITE)
        .grant("name-matcher", "hit.*", Level.WRITE)
        .grant("alert-triager", "alert.disposition", Level.WRITE)
        .grant("alert-triager", "alert.cleared_true_match", Level.NEVER)
        .grant("filing-writer", "sar.draft", Level.WRITE)
    )


def _listed(state: dict) -> list[str]:
    """The real SDN list unless the caller supplied one (the unit tests do)."""
    if state.get("listed") is not None:
        return state["listed"]
    return [e.primary for e in individuals()]


def triage(state: dict) -> dict:
    """Deterministic screening. The model only ever sees the alert backlog."""
    hits = screen(state.get("name", ""), _listed(state))
    return {
        "hits": [h.listed for h in hits],
        "hit_count": len(hits),
        "summary_subject": [h.listed for h in hits],
    }


def early_exit(state: dict) -> bool:
    """No screening hit is the common case and it costs nothing."""
    return state.get("hit_count", 0) == 0


def on_exit(state: dict) -> dict:
    return {"cleared": True, "reason": "no screening hit"}


def commit(state: dict) -> dict:
    """A drafted filing. Filing itself is a human, regulated action."""
    return {"sar.draft": state.get("draft", ""), "filed": False}


def _sdn(state: dict) -> list[str]:
    """Entity numbers behind the hits. Real OFAC records, as receipts."""
    listed = {e.primary: e.ent_num for e in individuals()}
    return sorted({listed[h] for h in state.get("hits", []) if h in listed})


def _aliases(state: dict) -> list[str]:
    """Known aliases of the hit entities, from OFAC's own ALT export."""
    by_name = {e.primary: e for e in individuals()}
    out: list[str] = []
    for hit in state.get("hits", []):
        entity = by_name.get(hit)
        if entity:
            out.extend(entity.aliases)
    return sorted(set(out))


def default_sources() -> dict:
    """Both branches read the committed OFAC exports."""
    return {"sdn": _sdn, "aliases": _aliases}
