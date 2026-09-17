"""Classify what a DDL statement does, and whether it can be undone.

Three categories, and the distinction between the last two is the point:

  reversible  - `down` can restore both schema and data from the schema alone
  lossy       - `down` can restore the *schema*, but the data is gone and
                nothing in the migration pair preserves it
  blocking    - executes, but takes a lock that stops writes on a live table

"lossy" is the dangerous class because it looks fine in review. A dropped
column's down-migration recreates the column, the schemas compare equal, and
the values are NULL forever.

This is pattern matching over statement text, not a SQL parser. It runs
alongside the shadow round-trip in `shadow.py`, which is the part that
actually executes. Where they disagree, the round-trip is right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REVERSIBLE = "reversible"
LOSSY = "lossy"
BLOCKING = "blocking"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Operation:
    statement: str
    kind: str  # "create_table", "drop_column", ...
    category: str  # REVERSIBLE | LOSSY | BLOCKING | UNKNOWN
    target: str  # table or index name, best effort
    reason: str

    @property
    def is_lossy(self) -> bool:
        return self.category == LOSSY


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else "").strip().strip('"`[]')


# Ordered: the first pattern that matches wins, so specific forms come first.
_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        r"^\s*DROP\s+TABLE\b",
        "drop_table",
        LOSSY,
        "every row in the table is deleted; a down-migration recreates an empty table",
    ),
    (
        r"^\s*ALTER\s+TABLE\s+.+?\s+DROP\s+(?:COLUMN\s+)?",
        "drop_column",
        LOSSY,
        "the column's values are deleted; recreating the column restores NULLs",
    ),
    (
        r"^\s*TRUNCATE\b",
        "truncate",
        LOSSY,
        "all rows removed with no copy retained",
    ),
    (
        r"^\s*DELETE\s+FROM\b(?!.*\bWHERE\b)",
        "delete_all",
        LOSSY,
        "unqualified DELETE removes every row",
    ),
    (
        r"^\s*ALTER\s+TABLE\s+.+?\s+(?:ALTER|MODIFY)\s+(?:COLUMN\s+)?.+?\s+TYPE\b",
        "change_type",
        LOSSY,
        "a narrowing type change truncates values that no longer fit",
    ),
    (
        r"^\s*ALTER\s+TABLE\s+.+?\s+RENAME\s+(?:COLUMN\s+)?",
        "rename",
        REVERSIBLE,
        "a rename carries the data with it and reverses exactly",
    ),
    (
        r"^\s*ALTER\s+TABLE\s+.+?\s+ADD\s+(?:COLUMN\s+)?.+?\bNOT\s+NULL\b"
        r"(?!.*\bDEFAULT\b)",
        "add_notnull_no_default",
        BLOCKING,
        "adding NOT NULL without a DEFAULT fails on any table that already has rows",
    ),
    (
        r"^\s*ALTER\s+TABLE\s+.+?\s+ADD\s+(?:COLUMN\s+)?",
        "add_column",
        REVERSIBLE,
        "the column did not exist before, so dropping it loses nothing that was there",
    ),
    (
        r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+CONCURRENTLY)",
        "create_index",
        BLOCKING,
        "builds the index under a lock; use CONCURRENTLY on a live table",
    ),
    (
        r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+CONCURRENTLY\b",
        "create_index_concurrently",
        REVERSIBLE,
        "built without blocking writes",
    ),
    (r"^\s*DROP\s+INDEX\b", "drop_index", REVERSIBLE, "an index can be rebuilt from the data"),
    (
        r"^\s*CREATE\s+TABLE\b",
        "create_table",
        REVERSIBLE,
        "the table did not exist before, so dropping it loses nothing that was there",
    ),
    (
        r"^\s*UPDATE\b",
        "update",
        LOSSY,
        "overwrites values in place with no copy of the previous ones",
    ),
    (r"^\s*INSERT\b", "insert", REVERSIBLE, "added rows can be deleted again"),
)


def classify(statement: str) -> Operation:
    text = statement.strip()
    for pattern, kind, category, reason in _RULES:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            return Operation(
                statement=text,
                kind=kind,
                category=category,
                target=_target_of(text, kind),
                reason=reason,
            )
    return Operation(
        statement=text,
        kind="other",
        category=UNKNOWN,
        target="",
        reason="not recognised; the shadow round-trip is the authority for this one",
    )


def _target_of(text: str, kind: str) -> str:
    if kind in ("create_index", "create_index_concurrently", "drop_index"):
        return _first(r"INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)", text)
    if kind == "create_table":
        return _first(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)", text)
    if kind == "drop_table":
        return _first(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([^\s;]+)", text)
    if kind in ("insert", "delete_all"):
        return _first(r"(?:INTO|FROM)\s+([^\s(;]+)", text)
    if kind == "update":
        return _first(r"UPDATE\s+([^\s;]+)", text)
    if kind == "truncate":
        return _first(r"TRUNCATE\s+(?:TABLE\s+)?([^\s;]+)", text)
    return _first(r"ALTER\s+TABLE\s+([^\s]+)", text)


def classify_script(script: str) -> list[Operation]:
    from .shadow import split_statements

    return [classify(s) for s in split_statements(script)]


def summarise(operations: list[Operation]) -> dict[str, int]:
    out: dict[str, int] = {}
    for op in operations:
        out[op.category] = out.get(op.category, 0) + 1
    return out
