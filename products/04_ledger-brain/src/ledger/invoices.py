"""Real invoices, and how often two of them carry the same amount.

`products/data/invoices.csv` is 54,716 invoice totals derived once from UCI's
Online Retail II by `scripts/make_invoices.py`. The source is a 45 MB
spreadsheet; what this product needs is one row per invoice, so the committed
artefact is small and this module reads it with the standard library.

Amounts are in minor units. Floats do not belong in money, and the question
this module exists to ask — do two invoices carry *exactly* the same amount —
is precisely the one a rounding difference would answer for you.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .domain import Invoice

DATA = Path(__file__).resolve().parents[3] / "data"
LEDGER = DATA / "invoices.csv"


class LedgerMissingError(FileNotFoundError):
    """The invoice extract is not on disk. Run scripts/make_invoices.py."""


@dataclass(frozen=True)
class Row:
    sheet: str
    invoice: str
    amount: int  # minor units
    lines: int
    date: str
    customer: str
    country: str

    @property
    def is_credit(self) -> bool:
        return self.amount < 0

    @property
    def nets_to_zero(self) -> bool:
        """A cancellation: line items that cancel each other out exactly."""
        return self.amount == 0


@lru_cache(maxsize=1)
def read(path: str | None = None) -> tuple[Row, ...]:
    target = Path(path) if path else LEDGER
    if not target.exists():
        raise LedgerMissingError(
            f"{target} is missing. Build it with: python scripts/make_invoices.py"
        )
    with target.open(encoding="utf-8", newline="") as fh:
        return tuple(
            Row(
                sheet=r["sheet"],
                invoice=r["invoice"],
                amount=int(r["amount_minor"]),
                lines=int(r["lines"]),
                date=r["date"],
                customer=r["customer"],
                country=r["country"],
            )
            for r in csv.DictReader(fh)
        )


def receivables(path: str | None = None) -> list[Row]:
    """Invoices someone is expected to pay: positive totals only.

    Credits and cancellations are a different reconciliation problem and mixing
    them in flatters the headline, because a zero-total invoice collides with
    every other zero-total invoice.
    """
    return [r for r in read(path) if r.amount > 0]


def as_invoices(rows: list[Row]) -> list[Invoice]:
    return [Invoice(r.invoice, r.amount) for r in rows]


@dataclass(frozen=True)
class Collisions:
    population: int
    distinct_amounts: int
    colliding_amounts: int
    invoices_in_collision: int
    largest_group: int

    @property
    def collision_rate(self) -> float:
        return self.invoices_in_collision / self.population

    @property
    def guess_accuracy(self) -> float:
        """How often picking one of the tied invoices is right.

        A matcher that resolves a tie by choosing is right ``1/n`` of the time
        for a group of ``n``; this is that, weighted across the population.
        """
        return self._weighted

    _weighted: float = 0.0


def collisions(rows: list[Row]) -> Collisions:
    """How often an amount fails to identify an invoice."""
    counts = Counter(r.amount for r in rows)
    colliding = {a: n for a, n in counts.items() if n > 1}
    in_collision = sum(colliding.values())
    weighted = (
        sum(n * (1 / n) for n in colliding.values()) / in_collision if in_collision else 1.0
    )
    return Collisions(
        population=len(rows),
        distinct_amounts=len(counts),
        colliding_amounts=len(colliding),
        invoices_in_collision=in_collision,
        largest_group=max(colliding.values(), default=1),
        _weighted=weighted,
    )


def headline_accuracy(rows: list[Row]) -> float:
    """What an amount-only matcher scores overall, guessing on every tie.

    The number a demo reports. It is the average of "always right on the unique
    half" and "a coin toss on the other half", and it hides the second half
    completely.
    """
    c = collisions(rows)
    unique = c.population - c.invoices_in_collision
    return (unique + c.invoices_in_collision * c.guess_accuracy) / c.population
