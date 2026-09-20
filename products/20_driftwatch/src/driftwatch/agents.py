"""driftwatch agents: change watching, claim extraction, verification, patching.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Claim, broken, verifiable_share, verify
from .repos import scan


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("change-watcher", "change.*", Level.WRITE)
        .grant("claim-extractor", "claim.*", Level.WRITE)
        .grant("verifier", "verdict.*", Level.WRITE)
        .grant("patch-writer", "patch.draft", Level.WRITE)
        .grant("pr-opener", "pull_request.merged", Level.NEVER)
    )


def _subject(state: dict) -> tuple[list, dict]:
    """The claims and facts for one repository.

    Reads the real checkout unless the caller passed claims directly, which is
    what the unit tests do to pin specific behaviour.
    """
    if state.get("readme_claims") is not None:
        return (
            [Claim(c) for c in state["readme_claims"]],
            state.get("facts", {}),
        )
    wanted = state.get("repo")
    for repo in scan(state.get("root")):
        if wanted in (None, repo.name):
            return [Claim(c) for c in repo.claims], repo.facts
    return [], {}


def triage(state: dict) -> dict:
    """Split claims into what a machine can settle and what it cannot."""
    claims, facts = _subject(state)
    if not claims:
        return {"verifiable_share": 0.0, "broken": [], "summary_subject": []}
    verdicts = [verify(c, facts) for c in claims]
    failing = broken(verdicts)
    return {
        "verifiable_share": round(verifiable_share(claims), 4),
        "broken": [v.claim.text for v in failing],
        "summary_subject": [v.claim.text for v in failing],
    }


def early_exit(state: dict) -> bool:
    """Every claim still holds. There is no pull request to open."""
    return not state.get("broken")


def on_exit(state: dict) -> dict:
    return {"no_drift": True, "reason": "every checkable claim still holds"}


def commit(state: dict) -> dict:
    return {"patch.draft": state.get("draft", ""), "merged": False}


def _facts(state: dict) -> list[str]:
    """The collected facts backing each verdict. Real, from the real checkout."""
    _, facts = _subject(state)
    return sorted(f"{k}={facts[k]}" for k in sorted(facts) if k != "root")


def _evidence(state: dict) -> list[str]:
    """The failing verdicts themselves, as receipts."""
    claims, facts = _subject(state)
    return sorted(v.detail for v in broken([verify(c, facts) for c in claims]))


def default_sources() -> dict:
    """Both branches read the real repository."""
    return {"facts": _facts, "evidence": _evidence}
