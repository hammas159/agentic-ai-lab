"""Forecast arithmetic, and detecting when an agent overwrote a person.

Two things the model is never allowed to do here: produce a forecast figure, and
change a field a human set more recently than any agent did.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_WEIGHTS: dict[str, float] = {
    "sourced": 0.05,
    "qualified": 0.20,
    "proposal": 0.50,
    "closing": 0.80,
    "won": 1.00,
    "lost": 0.00,
}

HUMAN = "human"


class UnknownStageError(KeyError):
    """A deal sits in a stage with no agreed weight. Refuse rather than guess."""


@dataclass(frozen=True)
class Deal:
    id: str
    amount: float
    stage: str


def weighted_forecast(deals: list[Deal], weights: dict[str, float] | None = None) -> float:
    """Stage-weighted pipeline value.

    Every input is named and every weight is published, so a buyer can disagree
    with the number by disagreeing with a weight rather than with a model.
    """
    table = DEFAULT_WEIGHTS if weights is None else weights
    total = 0.0
    for deal in deals:
        if deal.stage not in table:
            raise UnknownStageError(deal.stage)
        if deal.amount < 0:
            raise ValueError(f"deal {deal.id} has a negative amount")
        total += deal.amount * table[deal.stage]
    return round(total, 2)


@dataclass(frozen=True)
class Edit:
    """One change to one field.

    ``seq`` is a sequence number rather than a timestamp: two edits inside the
    same second are ordinary, and worker clocks disagree.
    """

    seq: int
    field: str
    value: object
    author: str


@dataclass(frozen=True)
class Revert:
    field: str
    by: str
    human_value: object
    agent_value: object
    human_seq: int
    agent_seq: int


def detect_reverts(edits: list[Edit]) -> list[Revert]:
    """Agent edits that changed a value a human had set most recently.

    An agent correcting another agent is not a revert. An agent re-writing the
    same value a human chose is not a revert either.
    """
    last: dict[str, Edit] = {}
    found: list[Revert] = []
    for edit in sorted(edits, key=lambda e: e.seq):
        previous = last.get(edit.field)
        if (
            edit.author != HUMAN
            and previous is not None
            and previous.author == HUMAN
            and previous.value != edit.value
        ):
            found.append(
                Revert(
                    field=edit.field,
                    by=edit.author,
                    human_value=previous.value,
                    agent_value=edit.value,
                    human_seq=previous.seq,
                    agent_seq=edit.seq,
                )
            )
        last[edit.field] = edit
    return found


def revert_rate(edits: list[Edit]) -> float:
    """Reverts as a share of agent edits. The headline number of this product."""
    agent_edits = sum(1 for e in edits if e.author != HUMAN)
    if agent_edits == 0:
        return 0.0
    return len(detect_reverts(edits)) / agent_edits
