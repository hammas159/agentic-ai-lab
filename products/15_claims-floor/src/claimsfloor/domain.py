"""Which policy wording was in force on the loss date.

The failure this guards is invisible in the output: an answer that is fluent,
cites a real clause, and is reading a version that had not yet taken effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class NoVersionInForceError(LookupError):
    """No wording covered the loss date. Never silently the latest one."""


class OverlappingVersionsError(LookupError):
    """Two wordings claim the same day. A real thing after an endorsement."""


@dataclass(frozen=True)
class PolicyVersion:
    id: str
    effective_from: date
    effective_to: date | None  # None means still in force
    perils: frozenset
    exclusions: frozenset = frozenset()

    def __post_init__(self) -> None:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError(f"{self.id} ends before it begins")

    def covers_date(self, when: date) -> bool:
        if when < self.effective_from:
            return False
        return self.effective_to is None or when <= self.effective_to


def version_for(versions: list[PolicyVersion], loss_date: date) -> PolicyVersion:
    """The wording in force on ``loss_date``. Refuses rather than defaulting."""
    matches = [v for v in versions if v.covers_date(loss_date)]
    if not matches:
        raise NoVersionInForceError(f"no wording covered {loss_date.isoformat()}")
    if len(matches) > 1:
        raise OverlappingVersionsError(
            f"{loss_date.isoformat()} is covered by {sorted(v.id for v in matches)}"
        )
    return matches[0]


COVERED = "covered"
EXCLUDED = "excluded by the wording in force"
NOT_A_LISTED_PERIL = "not a peril this wording covers"


@dataclass(frozen=True)
class Coverage:
    covered: bool
    reason: str
    version_id: str


def assess(versions: list[PolicyVersion], loss_date: date, peril: str) -> Coverage:
    """Coverage, always naming the version it was decided under."""
    version = version_for(versions, loss_date)
    if peril in version.exclusions:
        return Coverage(False, EXCLUDED, version.id)
    if peril not in version.perils:
        return Coverage(False, NOT_A_LISTED_PERIL, version.id)
    return Coverage(True, COVERED, version.id)


def wrong_version_rate(retrieved: list[str], correct: list[str]) -> float:
    """How often retrieval handed the model a superseded wording."""
    if len(retrieved) != len(correct):
        raise ValueError("one retrieved version per claim is required")
    if not correct:
        return 0.0
    wrong = sum(1 for r, c in zip(retrieved, correct, strict=True) if r != c)
    return wrong / len(correct)
