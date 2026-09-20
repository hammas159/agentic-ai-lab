"""A human baseline for how much two renderings of the same content overlap.

This product's claim is that per-platform "voice adaptation" produces four
near-identical texts. Testing that needs a yardstick: how different *are* two
genuine renderings of one thing, when different people write them?

`products/data/ami_manual.zip` answers it. Each AMI meeting carries up to four
participant summaries — the same meeting, written up separately by each person
who was in it. Same content, same facts, four independent renderings, by humans
with no instruction to differ.

That is the number a platform adapter should be compared against. Overlap far
above it is not adaptation, it is reformatting.

The user's own posts are what this product will eventually measure. This is the
baseline that makes that measurement mean something, and it is available now.
"""

from __future__ import annotations

import re
import statistics
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET

from .domain import content_tokens

DATA = Path(__file__).resolve().parents[3] / "data"
ARCHIVE = DATA / "ami_manual.zip"

_NAME = re.compile(r"^(?P<meeting>[A-Za-z0-9]+)\.(?P<who>[A-Z])\.summ\.xml$")


class CorpusMissingError(FileNotFoundError):
    """The AMI summaries are not on disk."""


@dataclass(frozen=True)
class Rendering:
    meeting: str
    author: str
    text: str

    @property
    def tokens(self) -> set[str]:
        return set(content_tokens(self.text))


def overlap(a: Rendering, b: Rendering) -> float:
    """Share of the shorter rendering's content words present in the longer.

    Containment rather than Jaccard, matching `domain.overlap`: the question is
    how much of one text is already in the other, and a shorter text should not
    be rewarded for brevity.
    """
    ta, tb = a.tokens, b.tokens
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(small & large) / len(small)


@lru_cache(maxsize=1)
def renderings(archive: str | None = None) -> tuple[Rendering, ...]:
    path = Path(archive) if archive else ARCHIVE
    if not path.exists():
        raise CorpusMissingError(f"{path} is missing. Fetch the AMI manual annotations.")
    out: list[Rendering] = []
    with zipfile.ZipFile(path) as zf:
        for member in sorted(zf.namelist()):
            if not member.startswith("participantSummaries/"):
                continue
            match = _NAME.match(member.split("/")[-1])
            if not match:
                continue
            try:
                root = ET.fromstring(zf.read(member))
            except ET.ParseError:
                continue
            text = " ".join(
                (node.text or "").strip() for node in root.iter("sent")
            ).strip()
            if len(text.split()) >= 30:
                out.append(
                    Rendering(match.group("meeting"), match.group("who"), text)
                )
    return tuple(out)


def by_meeting(archive: str | None = None) -> dict[str, list[Rendering]]:
    grouped: dict[str, list[Rendering]] = defaultdict(list)
    for rendering in renderings(archive):
        grouped[rendering.meeting].append(rendering)
    return {k: v for k, v in grouped.items() if len(v) > 1}


@dataclass(frozen=True)
class Baseline:
    meetings: int
    same_pairs: int
    different_pairs: int
    same_median: float
    different_median: float

    @property
    def separation(self) -> float:
        """How much more two renderings of one meeting share than of two."""
        return self.same_median - self.different_median


def baseline(archive: str | None = None, limit: int = 400) -> Baseline:
    """Overlap within a meeting, against overlap across meetings."""
    grouped = by_meeting(archive)
    same: list[float] = []
    for rows in grouped.values():
        same.extend(overlap(a, b) for a, b in combinations(rows, 2))

    # The control: renderings of different meetings, which share only the
    # vocabulary of people describing a meeting.
    flat = [rows[0] for rows in grouped.values()]
    different = [
        overlap(a, b) for a, b in combinations(flat[: min(len(flat), 40)], 2)
    ]

    return Baseline(
        meetings=len(grouped),
        same_pairs=len(same),
        different_pairs=len(different),
        same_median=statistics.median(same) if same else 0.0,
        different_median=statistics.median(different) if different else 0.0,
    )
