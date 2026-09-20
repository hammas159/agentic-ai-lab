"""The redaction barrier, and proof that it held.

Dropping the identifying fields is the easy half. The name reappearing inside a
free-text summary is the half that quietly defeats blind scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

IDENTIFYING = (
    "name",
    "email",
    "phone",
    "address",
    "photo_url",
    "gender",
    "nationality",
    "date_of_birth",
    "marital_status",
)

FREE_TEXT = ("summary", "experience", "education", "cover_letter")

REDACTED = "[redacted]"

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


@dataclass
class Blind:
    view: dict[str, object] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)


def _scrub(text: str, secrets: list[str]) -> str:
    out = _PHONE.sub(REDACTED, _EMAIL.sub(REDACTED, text))
    for secret in secrets:
        if len(secret) < 3:
            continue
        out = re.sub(re.escape(secret), REDACTED, out, flags=re.IGNORECASE)
    return out


def blind_view(cv: dict) -> Blind:
    """Everything the scorer is allowed to see, and nothing else.

    Identifying keys are dropped, then their values are scrubbed out of every
    free-text field, because that is where they come back.
    """
    secrets: list[str] = []
    for key in IDENTIFYING:
        value = cv.get(key)
        if isinstance(value, str) and value:
            secrets.extend(part for part in value.split() if len(part) >= 3)

    out = Blind()
    for key, value in cv.items():
        if key in IDENTIFYING:
            out.removed.append(key)
            continue
        if key in FREE_TEXT and isinstance(value, str):
            out.view[key] = _scrub(value, secrets)
        else:
            out.view[key] = value
    return out


def leaks(blind: Blind, secrets: list[str]) -> list[str]:
    """Identifying strings that survived. Must be empty before scoring runs."""
    blob = " ".join(str(v) for v in blind.view.values()).lower()
    return sorted({s for s in secrets if len(s) >= 3 and s.lower() in blob})


@dataclass(frozen=True)
class Rubric:
    dimensions: tuple[str, ...]
    max_per_dimension: int = 5


def total(rubric: Rubric, scores: dict[str, int]) -> int:
    """Sum the dimensions in Python. The model never produces this number."""
    missing = set(rubric.dimensions) - set(scores)
    if missing:
        raise ValueError(f"unscored dimensions: {sorted(missing)}")
    extra = set(scores) - set(rubric.dimensions)
    if extra:
        raise ValueError(f"dimensions not in the rubric: {sorted(extra)}")
    for name, value in scores.items():
        if not 0 <= value <= rubric.max_per_dimension:
            raise ValueError(f"{name}={value} is outside 0..{rubric.max_per_dimension}")
    return sum(scores.values())


def score_delta(identified: int, blinded: int) -> int:
    """The headline number: how much the name was worth."""
    return identified - blinded
