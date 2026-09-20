"""Are these two spellings the same name.

Not a language-understanding problem. The same Urdu or Arabic name reaches a
sanctions list through several transliteration conventions and several byte
encodings that render identically, and normalising for that is arithmetic.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PARTICLES = frozenset({"al", "el", "bin", "ibn", "bint", "abu", "ab", "ul", "ud", "uz", "us"})

# Transliteration conventions that reach a list for one underlying name.
EQUIVALENTS: tuple[tuple[str, str], ...] = (
    ("mohammad", "muhammad"),
    ("mohammed", "muhammad"),
    ("muhammed", "muhammad"),
    ("mohamed", "muhammad"),
    ("mohd", "muhammad"),
    ("ph", "f"),
    ("kh", "k"),
    ("gh", "g"),
    ("dh", "d"),
    ("th", "t"),
    ("sh", "s"),
    ("ee", "i"),
    ("oo", "u"),
    ("ou", "u"),
    ("y", "i"),
    ("w", "v"),
)

_NON_LETTER = re.compile(r"[^a-z\s]")
_SPACES = re.compile(r"\s+")

MIN_TOKENS = 2


def fold(token: str) -> str:
    """One token reduced to its transliteration-insensitive form."""
    out = token
    for source, target in EQUIVALENTS:
        out = out.replace(source, target)
    # Collapse doubled letters last: haroon -> harun -> harun, hassan -> hasan.
    collapsed = []
    for char in out:
        if not collapsed or collapsed[-1] != char:
            collapsed.append(char)
    return "".join(collapsed)


PREFIXES = ("al", "el", "ul")


def _drop_leading_particle(token: str) -> str:
    """``alhassan`` -> ``hassan``, but ``ali`` stays ``ali``.

    Deliberately recall-over-precision, and only for these three prefixes. A
    screening miss is a fine; an extra candidate costs an analyst a minute.
    The guard is the remainder length: anything shorter than four characters is
    left alone, which is what keeps ``ali``, ``elm`` and ``ula`` intact.
    """
    for prefix in PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 4:
            return token[len(prefix):]
    return token


def normalise(name: str) -> tuple[str, ...]:
    """A name as a sorted tuple of folded tokens.

    Sorted because list order varies: "Khan Ayesha" and "Ayesha Khan" are one
    person. Particles are dropped because they are written attached or detached
    at random.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = _NON_LETTER.sub(" ", stripped.lower().replace("-", " "))
    tokens = [t for t in _SPACES.split(cleaned) if t and t not in PARTICLES]
    return tuple(sorted({_drop_leading_particle(fold(t)) for t in tokens if t}))


def same_person(a: str, b: str) -> bool:
    """True when two spellings normalise to the same set of name parts.

    A subset counts — lists routinely hold a two-part name for someone recorded
    elsewhere with three — but never below ``MIN_TOKENS``, or every Ahmed on
    earth matches every other.
    """
    na, nb = set(normalise(a)), set(normalise(b))
    if len(na) < MIN_TOKENS or len(nb) < MIN_TOKENS:
        return na == nb and len(na) >= MIN_TOKENS
    return na <= nb or nb <= na


@dataclass(frozen=True)
class Hit:
    listed: str
    matched_on: tuple[str, ...]


def screen(name: str, listed: list[str]) -> list[Hit]:
    """Every list entry this name could be. Recall first; a human sifts."""
    return [Hit(entry, normalise(entry)) for entry in listed if same_person(name, entry)]


def alias_recall(found: set[str], truth: set[str]) -> float:
    """Share of the real aliases a matcher found. Undefined on an empty truth set."""
    if not truth:
        raise ValueError("recall is undefined with no true aliases")
    return len(found & truth) / len(truth)
