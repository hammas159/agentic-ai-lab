"""hermes-home agents: conversation, memory proposal, contradiction checking.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Constraint, ConstraintDroppedError, Handoff, prepare, verify
from .locomo import coverage as _coverage
from .locomo import load as _locomo


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("conversation", "message.*", Level.WRITE)
        .grant("memory-proposer", "memory.candidate", Level.WRITE)
        .grant("memory-proposer", "memory.stored", Level.NEVER)
        .grant("contradiction-checker", "memory.stored", Level.WRITE)
        .grant("skill-author", "skill.draft", Level.WRITE)
    )


def _constraints(state: dict) -> list[Constraint]:
    return [
        Constraint(c["id"], c["predicate"], c["value"], c["hard"])
        for c in state.get("constraints", [])
    ]


def triage(state: dict) -> dict:
    """A handoff carries every constraint, and is refused if a hard one is lost."""
    known = _constraints(state)
    handoff = prepare(state.get("specialist", "specialist"), state.get("message", ""), known)
    carried = set(handoff.carried)
    if state.get("drop_hard"):
        handoff = Handoff(handoff.to, handoff.message, [c for c in known if not c.hard])
        carried = set(handoff.carried)
    try:
        soft_lost = verify(known, handoff)
        return {
            "carried": sorted(carried),
            "soft_lost": [c.id for c in soft_lost],
            "hard_dropped": False,
            "summary_subject": sorted(carried),
        }
    except ConstraintDroppedError as refused:
        return {"hard_dropped": True, "refusal": str(refused), "summary_subject": []}


def early_exit(state: dict) -> bool:
    """A handoff that would lose a hard constraint does not proceed."""
    return bool(state.get("hard_dropped"))


def on_exit(state: dict) -> dict:
    return {"handoff_refused": True, "reason": state.get("refusal", "")}


def commit(state: dict) -> dict:
    return {"reply": state.get("draft", ""), "memory_written": False}


def _horizon(state: dict) -> list[str]:
    """What a sliding window would lose, measured on LoCoMo. Real receipts."""
    return [f"window_{w}_coverage={_coverage(w):.4f}" for w in (1, 3, 8)]


def _sessions(state: dict) -> list[str]:
    """The conversations the horizon was measured over."""
    return sorted(f"{c.sample_id}:{c.sessions}sessions" for c in _locomo())


def default_sources() -> dict:
    """Both branches read the committed LoCoMo benchmark."""
    return {"horizon": _horizon, "sessions": _sessions}
