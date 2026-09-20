"""bid-desk agents: crawling, requirement extraction, compliance, proposal.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Requirement, evaluate
from .rfc import compare_mandatory as _compare
from .rfc import mandatory_only as _mandatory
from .rfc import strict as _strict


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("crawler", "tender.*", Level.WRITE)
        .grant("requirement-extractor", "requirement.*", Level.WRITE)
        .grant("fit-scorer", "fit.score", Level.WRITE)
        .grant("fit-scorer", "bid.decision", Level.PROPOSE)
        .grant("proposal-writer", "section.*", Level.WRITE)
    )


def triage(state: dict) -> dict:
    """The checklist decides whether a bid is possible at all."""
    if state.get("requirements") is not None:
        requirements = [
            Requirement(r["id"], r["text"], r["mandatory"]) for r in state["requirements"]
        ]
    else:
        # Real requirements, from a real document, with RFC 2119 as the rule for
        # what binds. Same shape as a tender's compliance clauses.
        found = _strict()[: state.get("limit", 60)]
        requirements = [
            Requirement(f"{r.document}:{r.line}", r.text, r.mandatory) for r in found
        ]
    checklist = evaluate(requirements, set(state.get("evidenced", [])))
    return {
        "submittable": checklist.submittable,
        "missing_mandatory": checklist.missing_mandatory,
        "summary_subject": state.get("tender", ""),
    }


def early_exit(state: dict) -> bool:
    """One missing mandatory item means rejection unread. Do not write prose."""
    return not state.get("submittable", False)


def on_exit(state: dict) -> dict:
    return {"blocked": True, "missing": state.get("missing_mandatory", [])}


def commit(state: dict) -> dict:
    return {"section.draft": state.get("draft", ""), "submitted": False}


def _clauses(state: dict) -> list[str]:
    """The binding clauses themselves, cited by document and line."""
    return [f"{r.document}:{r.line}:{r.keyword}" for r in _mandatory(_strict())][:40]


def _extractor(state: dict) -> list[str]:
    """How a case-insensitive reader scores against the real rule."""
    c = _compare()
    return [
        f"recall={c.recall:.4f}",
        f"precision={c.precision:.4f}",
        f"false_positives={c.false_positives}",
    ]


def default_sources() -> dict:
    """Both branches read the committed RFC texts."""
    return {"clauses": _clauses, "extractor": _extractor}
