"""Deduplicating commitments that arrive from two sources in different words.

The merge is where this class of product quietly breaks: it either doubles the
task list or collapses two different people's promises into one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

_WORD = re.compile(r"[a-z0-9']+")

STOP = frozenset(
    ["a", "an", "and", "by", "for", "i", "in", "of", "on", "the", "to", "will", "would"]
)

MIN_TOKENS = 4


@lru_cache(maxsize=200_000)
def tokens(text: str) -> frozenset[str]:
    """Content words, memoised.

    Every comparison re-tokenised both sides, so a corpus-wide run spent most of
    its time in `re.findall` on strings it had already seen. Caching is not a
    micro-optimisation here: it is the difference between a measurement that runs
    on the whole corpus and one quietly run on a twelve-meeting sample.

    Bounded, because this is imported by a long-running API: an unbounded cache
    keyed on arbitrary user text is a slow memory leak.
    """
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in STOP)


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

    Blocked on (speaker, token) rather than compared pairwise. The naive version
    is quadratic and could not finish the full AMI corpus at all — which is how
    a measurement ends up quietly run on a twelve-meeting sample instead of the
    whole thing. Two texts below the threshold must still share at least one
    content word, so indexing by token loses nothing and skips the rest.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")

    clusters: list[Cluster] = []
    # (speaker, token) -> indices of clusters containing that token
    index: dict[tuple[str, str], set[int]] = {}

    for item in commitments:
        item_tokens = tokens(item.text)
        candidates: set[int] = set()
        if len(item_tokens) >= MIN_TOKENS:
            for token in item_tokens:
                candidates |= index.get((item.speaker, token), set())

        # Jaccard >= t forces min(|A|,|B|) >= t * max(|A|,|B|), so anything
        # outside this band cannot reach the threshold and need not be scored.
        size = len(item_tokens)
        low, high = threshold * size, size / threshold

        placed = False
        for position in sorted(candidates):
            cluster = clusters[position]
            if any(
                low <= len(tokens(other.text)) <= high
                and similarity(item.text, other.text) >= threshold
                for other in cluster.items
            ):
                cluster.items.append(item)
                placed = True
                break

        if not placed:
            position = len(clusters)
            clusters.append(Cluster([item]))

        for token in item_tokens:
            index.setdefault((item.speaker, token), set()).add(position)

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
