"""The five-topic convention, and partitioning that survives a restart.

Every product uses the same five topics under its own domain prefix. Keying by
entity id gives per-entity ordering for free: two agents can never process the
same deal, patient or claim out of order, because they land on the same
partition.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

SUFFIXES = ("intake", "tasks", "events", "approvals", "dlq")

_DOMAIN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class InvalidDomainError(ValueError):
    """The domain prefix is not a legal topic name component."""


@dataclass(frozen=True)
class Topics:
    """The five topics belonging to one product."""

    domain: str

    def __post_init__(self) -> None:
        if not _DOMAIN.match(self.domain):
            raise InvalidDomainError(
                f"{self.domain!r} must be lower case, start with a letter, "
                "and separate words with single hyphens"
            )

    def name(self, suffix: str) -> str:
        if suffix not in SUFFIXES:
            raise ValueError(f"{suffix!r} is not one of {SUFFIXES}")
        return f"{self.domain}.{suffix}"

    @property
    def intake(self) -> str:
        return self.name("intake")

    @property
    def tasks(self) -> str:
        return self.name("tasks")

    @property
    def events(self) -> str:
        return self.name("events")

    @property
    def approvals(self) -> str:
        return self.name("approvals")

    @property
    def dlq(self) -> str:
        return self.name("dlq")

    def all(self) -> tuple[str, ...]:
        return tuple(self.name(s) for s in SUFFIXES)


def partition_key(entity_type: str, entity_id: str) -> str:
    """The message key. Same entity, same key, therefore same partition."""
    if not entity_type or not entity_id:
        raise ValueError("both entity_type and entity_id are required")
    return f"{entity_type}:{entity_id}"


def partition_for(key: str, partitions: int) -> int:
    """Pick a partition for a key.

    Deliberately crc32 and not the built-in ``hash``. Python salts ``hash`` per
    process (PYTHONHASHSEED), so a consumer restarted tomorrow would map the
    same key to a different partition and silently lose per-entity ordering.
    That is the kind of bug that only appears under a rolling restart.
    """
    if partitions < 1:
        raise ValueError("partitions must be at least 1")
    return zlib.crc32(key.encode("utf-8")) % partitions
