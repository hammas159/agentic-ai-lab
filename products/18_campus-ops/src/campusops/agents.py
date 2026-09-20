"""campus-ops agents: admissions, scheduling, fees, parent communications.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Session, clashes, publishable
from .schedule import clashes_by_day as _by_day
from .schedule import report as _report
from .schedule import sessions as _real_sessions


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("applicant-parser", "application.*", Level.WRITE)
        .grant("eligibility-checker", "eligibility", Level.WRITE)
        .grant("eligibility-checker", "offer", Level.NEVER)
        .grant("scheduler", "timetable.*", Level.WRITE)
        .grant("parent-comms", "message.draft", Level.WRITE)
    )


def triage(state: dict) -> dict:
    """Three clash types, not one. A timetable with any of them is not published."""
    if state.get("sessions") is not None:
        sessions = [
            Session(
                s["id"], s["day"], s["start"], s["end"], s["room"], s["teacher"], s["cohort"]
            )
            for s in state["sessions"]
        ]
    else:
        # A real day from the real schedule. Defaults to one that clashes,
        # because a clean day exercises nothing.
        clashing = sorted(d for d, c in _by_day().items() if c)
        day = state.get("day") or (clashing[0] if clashing else None)
        sessions = [s for s in _real_sessions() if s.day == day]
    found = clashes(sessions)
    return {
        "clashes": [(c.dimension, c.first, c.second) for c in found],
        "publishable": publishable(sessions),
        "summary_subject": sorted({c.dimension for c in found}),
    }


def early_exit(state: dict) -> bool:
    """A clashing timetable is refused, not annotated."""
    return not state.get("publishable", False)


def on_exit(state: dict) -> dict:
    return {"not_publishable": True, "clashes": state.get("clashes", [])}


def commit(state: dict) -> dict:
    return {"message.draft": state.get("draft", ""), "published": False}


def _bookings(state: dict) -> list[str]:
    """The sessions on the day under review. Real receipts."""
    clashing = sorted(d for d, c in _by_day().items() if c)
    day = state.get("day") or (clashing[0] if clashing else None)
    return sorted(f"{s.id}@{s.start}-{s.end}" for s in _real_sessions() if s.day == day)


def _prevalence(state: dict) -> list[str]:
    """How common each kind of clash is across the whole schedule."""
    r = _report()
    return [f"{k}={v}" for k, v in sorted(r.by_dimension.items())] + [
        f"clashing_days={r.clashing_days}",
        f"days={r.days}",
    ]


def default_sources() -> dict:
    """Both branches read the committed schedule."""
    return {"bookings": _bookings, "prevalence": _prevalence}
