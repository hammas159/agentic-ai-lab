"""ward-sync agents: intake, bed planning, result routing, discharge.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Event, active_medications, discontinued
from .synthea import medications as _synthea_meds


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("intake", "encounter.*", Level.WRITE)
        .grant("triage-router", ("encounter.department", "encounter.acuity_band"), Level.WRITE)
        .grant("bed-planner", "assignment.*", Level.WRITE)
        .grant("discharge-writer", "summary.draft", Level.WRITE)
        .grant("discharge-writer", "summary.final", Level.PROPOSE)
    )


def _events(state: dict) -> list[Event]:
    """The encounter's event stream.

    Supplied directly by the unit tests; otherwise rebuilt from real Synthea
    records, where every prescription carries a START and, usually, a STOP.
    """
    if state.get("events") is not None:
        return [Event(e["id"], e["seq"], e["kind"], e["drug"]) for e in state["events"]]

    patient = state.get("patient")
    rows = [m for m in _synthea_meds() if patient in (None, m.patient)]
    if patient is None and rows:
        patient = rows[0].patient
        rows = [m for m in rows if m.patient == patient]

    events, seq = [], 0
    for med in sorted(rows, key=lambda m: m.start):
        seq += 1
        events.append(Event(f"start_{seq}", seq, "ordered", med.description))
        if med.stopped:
            seq += 1
            events.append(Event(f"stop_{seq}", seq, "discontinued", med.description))
    return events


def triage(state: dict) -> dict:
    """Medication state comes from the event stream, never the current list."""
    events = _events(state)
    active = active_medications(events)
    return {
        "active_medications": [a.drug for a in active],
        "must_not_mention": sorted(discontinued(events)),
        "summary_subject": state.get("encounter", ""),
    }


def early_exit(state: dict) -> bool:
    """An encounter with no recorded events cannot be summarised, only escalated."""
    return not state.get("events")


def on_exit(state: dict) -> dict:
    return {"escalated": True, "reason": "no events recorded for this encounter"}


def commit(state: dict) -> dict:
    """A draft, never a signed summary. A clinician signs."""
    return {"summary.draft": state.get("draft", ""), "signed": False}


def _orders(state: dict) -> list[str]:
    """Event ids for medications still in force. Real receipts from the stream."""
    return sorted(a.evidence for a in active_medications(_events(state)))


def _stopped(state: dict) -> list[str]:
    """Drugs a summary must not name. Also evidence, and the useful half."""
    return sorted(discontinued(_events(state)))


def default_sources() -> dict:
    """Both branches read the encounter's own event stream."""
    return {"orders": _orders, "stopped": _stopped}
