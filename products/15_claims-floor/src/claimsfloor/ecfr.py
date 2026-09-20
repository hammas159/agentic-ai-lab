"""Real versioned regulation, and the question a retriever gets wrong.

`products/data/ecfr_title29.json` is the eCFR version index for Title 29
(Labor): 1,000 real section versions, each with the date its amendment took
effect. Sections are amended repeatedly, so a section has a *history*, and
"which text was in force on date D" has a definite answer.

That is structurally the same problem as an insurance policy wording, and it is
the one this product exists to get right. A retriever that returns the current
text of a section answers a different question from the one asked about a loss
that happened four years ago — fluently, citing a real section, and wrong.

Regulation stands in for policy wordings because insurers do not publish a
machine-readable archive of superseded wordings, and inventing one would make
the measurement worthless.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
INDEX = DATA / "ecfr_title29.json"


class IndexMissingError(FileNotFoundError):
    """The eCFR version index is not on disk."""


@dataclass(frozen=True)
class Version:
    identifier: str          # the section, e.g. "1910.1200"
    effective: date
    name: str
    removed: bool
    substantive: bool

    @property
    def section(self) -> str:
        return self.identifier


def _parse(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def versions(path: str | None = None) -> tuple[Version, ...]:
    target = Path(path) if path else INDEX
    if not target.exists():
        raise IndexMissingError(f"{target} is missing. Fetch the eCFR version index.")
    payload = json.loads(target.read_text(encoding="utf-8"))
    out: list[Version] = []
    for row in payload.get("content_versions", []):
        effective = _parse(row.get("amendment_date") or row.get("date"))
        identifier = row.get("identifier")
        if effective is None or not identifier:
            continue
        out.append(
            Version(
                identifier=identifier,
                effective=effective,
                name=row.get("name", ""),
                removed=bool(row.get("removed")),
                substantive=bool(row.get("substantive")),
            )
        )
    return tuple(out)


@lru_cache(maxsize=1)
def history(path: str | None = None) -> dict[str, list[Version]]:
    """Section -> its versions, oldest first."""
    out: dict[str, list[Version]] = defaultdict(list)
    for version in versions(path):
        out[version.identifier].append(version)
    return {k: sorted(v, key=lambda x: x.effective) for k, v in out.items()}


def amended(path: str | None = None) -> dict[str, list[Version]]:
    """Only the sections that were actually amended more than once."""
    return {k: v for k, v in history(path).items() if len(v) > 1}


def in_force(section: str, on: date, path: str | None = None) -> Version | None:
    """The version in force on a date. The correct answer."""
    rows = history(path).get(section)
    if not rows:
        return None
    dates = [r.effective for r in rows]
    index = bisect_right(dates, on) - 1
    return rows[index] if index >= 0 else None


def latest(section: str, path: str | None = None) -> Version | None:
    """The current version. What a retriever returns when nobody asked it not to."""
    rows = history(path).get(section)
    return rows[-1] if rows else None


@dataclass(frozen=True)
class Mismatch:
    section: str
    asked_on: date
    correct: date
    returned: date

    @property
    def years_out(self) -> float:
        return (self.returned - self.correct).days / 365.25


def wrong_version_rate(path: str | None = None) -> tuple[float, list[Mismatch]]:
    """How often "return the current text" answers the wrong question.

    Asked once per (amended section, each date its own history makes
    meaningful) — that is, for every version of every amended section, ask what
    was in force the day it took effect.
    """
    mismatches: list[Mismatch] = []
    asked = 0
    for section, rows in amended(path).items():
        newest = rows[-1]
        for row in rows:
            asked += 1
            correct = in_force(section, row.effective, path)
            if correct and correct.effective != newest.effective:
                mismatches.append(
                    Mismatch(section, row.effective, correct.effective, newest.effective)
                )
    return (len(mismatches) / asked if asked else 0.0), mismatches
