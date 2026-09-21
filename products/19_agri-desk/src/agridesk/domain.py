"""Counting variants without counting the same isolate several times.

``clcuv-surveillance`` found that collapsing clonal duplicates turned nine
"emerging variants" into zero. An advisory agent reading the uncollapsed feed
warns about an outbreak that is not happening.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# GenBank omits the country on some records. It is the absence of a location,
# never a place, and must never satisfy a multi-site requirement.
UNKNOWN_SITE = "unknown"


@dataclass(frozen=True)
class Isolate:
    id: str
    sequence: str
    site: str
    day: int

    def __post_init__(self) -> None:
        if not self.sequence:
            raise ValueError(f"isolate {self.id} has no sequence")


@dataclass
class Cluster:
    """One biological observation, however many times it was sequenced."""

    sequence: str
    site: str
    members: list = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def first_seen(self) -> int:
        return min(m.day for m in self.members)

    @property
    def clonal(self) -> bool:
        return self.size > 1


def collapse_clonal(isolates: list[Isolate]) -> list[Cluster]:
    """Group identical sequences from one site.

    Site is part of the key on purpose: the same sequence at two distant sites
    is two observations, and collapsing those hides real spread.
    """
    groups: dict[tuple[str, str], Cluster] = {}
    for isolate in sorted(isolates, key=lambda i: (i.day, i.id)):
        key = (isolate.sequence, isolate.site)
        cluster = groups.get(key)
        if cluster is None:
            cluster = Cluster(isolate.sequence, isolate.site)
            groups[key] = cluster
        cluster.members.append(isolate)
    return [groups[k] for k in sorted(groups)]


def distinct_variants(isolates: list[Isolate], collapse: bool = True) -> int:
    """Variant count, with and without collapsing. The comparison is the point."""
    if not collapse:
        return len(isolates)
    return len(collapse_clonal(isolates))


def emerging(isolates: list[Isolate], since_day: int, min_sites: int = 2) -> list[str]:
    """Sequences newly seen since ``since_day`` at ``min_sites`` or more sites.

    Requiring several sites is the second guard: one site sequencing the same
    thing repeatedly is not emergence, whatever the count says.

    A record with no location contributes no site. GenBank leaves the country
    off 31 of the 898 genomes here, and counting ``unknown`` as a place lets a
    single-site variant reach two sites by being partly unlabelled — the exact
    false positive this function exists to remove, re-entering through the
    missing-data door.
    """
    if min_sites < 1:
        raise ValueError("emergence needs at least one site")
    clusters = collapse_clonal(isolates)
    sites: dict[str, set[str]] = {}
    earliest: dict[str, int] = {}
    for cluster in clusters:
        sites.setdefault(cluster.sequence, set())
        if cluster.site != UNKNOWN_SITE:
            sites[cluster.sequence].add(cluster.site)
        earliest[cluster.sequence] = min(
            earliest.get(cluster.sequence, cluster.first_seen), cluster.first_seen
        )
    return sorted(
        seq
        for seq, where in sites.items()
        if len(where) >= min_sites and earliest[seq] >= since_day
    )


def false_alarm_rate(isolates: list[Isolate], since_day: int, min_sites: int = 2) -> float:
    """Share of uncollapsed 'emerging' calls that survive collapsing.

    Returns the share that were spurious, which is the number the README owes.
    """
    naive = {i.sequence for i in isolates if i.day >= since_day}
    if not naive:
        return 0.0
    real = set(emerging(isolates, since_day, min_sites))
    return len(naive - real) / len(naive)
