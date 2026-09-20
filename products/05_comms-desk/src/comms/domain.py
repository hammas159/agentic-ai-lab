"""Deduplicating commitments that arrive from two sources in different words.

The merge is where this class of product quietly breaks: it either doubles the
task list or collapses two different people's promises into one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORD = re.compile(r"[a-z0-9']+")

STOP = frozenset(
    ["a", "an", "and", "by", "for", "i", "in", "of", "on", "the", "to", "will", "would"]
)

MIN_TOKENS = 4


def tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP}


def similarity(a: str, b: str) -> float:
    """Jaccard over content words. Zero when either side is too short."""
    ta, tb = tokens(a), tokens(b)
    if len(ta) < MIN_TOKENS or len(tb) < MIN_TOKENS:
        return 0.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


@dataclass(frozen=True)
class Commitment:
    id: str
    speaker: str
    text: str
    source: str  # "meeting" or "email"


@dataclass
class Cluster:
    items: list[Commitment] = field(default_factory=list)

    @property
    def speaker(self) -> str:
        return self.items[0].speaker

    @property
    def sources(self) -> set[str]:
        return {i.source for i in self.items}

    @property
    def is_duplicate(self) -> bool:
        return len(self.items) > 1


def dedupe(commitments: list[Commitment], threshold: float = 0.6) -> list[Cluster]:
    """Group commitments that are the same promise.

    Speaker is a hard barrier, never a weighted feature: two people making
    similar promises made two promises. That is the over-merge this guards.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    clusters: list[Cluster] = []
    for item in commitments:
        for cluster in clusters:
            if cluster.speaker != item.speaker:
                continue
            if any(similarity(item.text, other.text) >= threshold for other in cluster.items):
                cluster.items.append(item)
                break
        else:
            clusters.append(Cluster([item]))
    return clusters


def duplicate_rate(commitments: list[Commitment], threshold: float = 0.6) -> float:
    """Share of raw commitments that were a restatement of another."""
    if not commitments:
        return 0.0
    clusters = dedupe(commitments, threshold)
    return (len(commitments) - len(clusters)) / len(commitments)


def cross_source(clusters: list[Cluster]) -> list[Cluster]:
    """Clusters proved by both a meeting and an email. The strongest evidence."""
    return [c for c in clusters if len(c.sources) > 1]
