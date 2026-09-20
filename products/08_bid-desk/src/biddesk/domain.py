"""Whether the bid can be submitted at all, and how long is left.

A tender is scored on prose and rejected on a checkbox. This module is the
checkbox half, which is why nothing in it is a model call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    mandatory: bool
    cite: str = ""


@dataclass
class Checklist:
    satisfied: list[str] = field(default_factory=list)
    missing_mandatory: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)

    @property
    def submittable(self) -> bool:
        """No partial credit. A tender portal does not offer any."""
        return not self.missing_mandatory


def evaluate(requirements: list[Requirement], evidenced: set[str]) -> Checklist:
    """Check supplied evidence against the requirements pulled from the tender."""
    out = Checklist()
    for requirement in requirements:
        if requirement.id in evidenced:
            out.satisfied.append(requirement.id)
        elif requirement.mandatory:
            out.missing_mandatory.append(requirement.id)
        else:
            out.missing_optional.append(requirement.id)
    return out


def mandatory_recall(found: set[str], truth: list[Requirement]) -> float:
    """Share of the real mandatory items an extractor actually found.

    The metric this product lives or dies by. Overall recall hides it, because
    mandatory items are a minority of every tender.
    """
    mandatory = {r.id for r in truth if r.mandatory}
    if not mandatory:
        raise ValueError("this tender has no mandatory items; recall is undefined")
    return len(found & mandatory) / len(mandatory)


def days_to_deadline(today: date, deadline: date) -> int:
    """Whole days remaining. Negative once the tender has closed.

    Date arithmetic, never a model. A model got a month boundary wrong on an
    eight-figure tender, which is why this function exists.
    """
    return (deadline - today).days


def urgency(today: date, deadline: date) -> str:
    days = days_to_deadline(today, deadline)
    if days < 0:
        return "closed"
    if days <= 3:
        return "urgent"
    if days <= 10:
        return "soon"
    return "watching"
