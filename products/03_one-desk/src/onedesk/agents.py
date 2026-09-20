"""one-desk agents: planning, per-platform adaptation, comment triage.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import compare
from .variants import baseline as _baseline
from .variants import by_meeting as _by_meeting


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("planner", "calendar.*", Level.WRITE)
        .grant("adapter", "variant.*", Level.WRITE)
        .grant("adapter", "post.published", Level.NEVER)
        .grant("brand-guard", "veto", Level.WRITE)
        .grant("analyst", "metrics.*", Level.WRITE)
    )


def triage(state: dict) -> dict:
    """Measure how derivative each variant is before anyone calls it adaptation.

    Against the human baseline: independent renderings of identical content
    overlap at about 0.23. See :mod:`onedesk.variants`.
    """
    if not state.get("baseline"):
        grouped = _by_meeting()
        meeting = state.get("meeting") or sorted(grouped)[0]
        rows_in = grouped.get(meeting, [])
        if len(rows_in) > 1:
            state = {
                **state,
                "idea": meeting,
                "baseline": rows_in[0].text,
                "variants": {r.author: r.text for r in rows_in[1:]},
            }
    rows = compare(state.get("baseline", ""), state.get("variants", {}))
    return {
        "overlaps": {r.platform: r.overlap for r in rows},
        "max_overlap": max((r.overlap for r in rows), default=0.0),
        "summary_subject": state.get("idea", ""),
    }


def early_exit(state: dict) -> bool:
    """A brand veto stops the run before anything is generated."""
    return bool(state.get("brand_veto"))


def on_exit(state: dict) -> dict:
    return {"vetoed": True, "reason": state.get("brand_veto", "")}


def commit(state: dict) -> dict:
    """Scheduled, not published. Publishing is a human action."""
    return {"scheduled": True, "published": False}


def _human_baseline(state: dict) -> list[str]:
    """What independent renderings of one thing actually overlap at."""
    b = _baseline()
    return [
        f"same_meeting_median={b.same_median:.4f}",
        f"different_meeting_median={b.different_median:.4f}",
        f"pairs={b.same_pairs}",
    ]


def _renderings(state: dict) -> list[str]:
    """The renderings compared, cited by meeting and author."""
    grouped = _by_meeting()
    meeting = state.get("meeting") or (sorted(grouped)[0] if grouped else "")
    return [f"{r.meeting}.{r.author}" for r in grouped.get(meeting, [])]


def default_sources() -> dict:
    """Both branches read the committed AMI summaries."""
    return {"baseline": _human_baseline, "renderings": _renderings}
