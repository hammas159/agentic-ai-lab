"""Semantic memory whose writes are gated on contradiction.

Ungated writes are why long-lived agents rot. A fact is persisted only after it
survives a check against what is already stored; a contradiction is returned
for resolution rather than silently overwriting or silently duplicating.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Outcome(Enum):
    STORED = "stored"
    DUPLICATE = "duplicate"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True)
class Fact:
    subject: str
    predicate: str
    value: str
    source: str

    @property
    def slot(self) -> tuple[str, str]:
        return (self.subject, self.predicate)


@dataclass(frozen=True)
class Write:
    outcome: Outcome
    fact: Fact
    existing: Fact | None = None

    @property
    def stored(self) -> bool:
        return self.outcome is Outcome.STORED


class Semantic:
    """Facts keyed by (subject, predicate).

    ``hard`` predicates are ones where being wrong is not recoverable — an
    allergy, a dietary constraint, an accessibility requirement. A contradiction
    on a hard predicate is never auto-resolved, whatever the source.
    """

    def __init__(self, hard: set[str] | None = None) -> None:
        self._facts: dict[tuple[str, str], Fact] = {}
        self.hard = set(hard or ())

    def __len__(self) -> int:
        return len(self._facts)

    def get(self, subject: str, predicate: str) -> Fact | None:
        return self._facts.get((subject, predicate))

    def propose(self, fact: Fact) -> Write:
        """Check a candidate without storing it."""
        existing = self._facts.get(fact.slot)
        if existing is None:
            return Write(Outcome.STORED, fact)
        if existing.value == fact.value:
            return Write(Outcome.DUPLICATE, fact, existing)
        return Write(Outcome.CONTRADICTS, fact, existing)

    def write(self, fact: Fact) -> Write:
        """Store a candidate if it survives the contradiction check."""
        decision = self.propose(fact)
        if decision.outcome is Outcome.STORED:
            self._facts[fact.slot] = fact
        return decision

    def resolve(self, fact: Fact) -> Write:
        """Overwrite a contradicted slot deliberately, after a human decided.

        NotAuthorisedError on a hard predicate, where the correct action is to ask rather
        than to pick.
        """
        if fact.predicate in self.hard:
            raise PermissionError(
                f"{fact.predicate!r} is a hard constraint; a contradiction on it "
                "is resolved by a person, not by this call"
            )
        self._facts[fact.slot] = fact
        return Write(Outcome.STORED, fact)
