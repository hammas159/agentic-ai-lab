"""How many model workers this GPU can actually run.

The bus can have twelve partitions. The consumer group that calls the model
cannot, because there is one card and one model instance. Getting this wrong is
the most common way a local agent system falls over at concurrency three.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Gpu:
    """What is physically present."""

    total_mb: int
    model_mb: int
    kv_cache_mb_per_slot: int

    def __post_init__(self) -> None:
        if self.model_mb >= self.total_mb:
            raise ValueError("the model does not fit on this card")
        if self.kv_cache_mb_per_slot < 1:
            raise ValueError("a slot needs some KV cache")

    @property
    def max_slots(self) -> int:
        """Concurrent generations this card supports. Never zero; never a guess."""
        free = self.total_mb - self.model_mb
        return max(1, free // self.kv_cache_mb_per_slot)


@dataclass(frozen=True)
class Decision:
    admitted: bool
    reason: str = ""


ADMITTED = Decision(True)


class Controller:
    """Admission control in front of the model, not inside it.

    Checked before the message is handed to a worker, so a tenant over budget
    costs nothing rather than costing a generation that is then discarded.
    """

    def __init__(self, gpu: Gpu, daily_token_budget: dict[str, int] | None = None) -> None:
        self.gpu = gpu
        self._budget = dict(daily_token_budget or {})
        self._used: dict[str, int] = {}
        self._in_flight = 0

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def used(self, tenant: str) -> int:
        return self._used.get(tenant, 0)

    def admit(self, tenant: str, estimated_tokens: int) -> Decision:
        if estimated_tokens < 0:
            raise ValueError("estimated_tokens cannot be negative")
        if self._in_flight >= self.gpu.max_slots:
            return Decision(False, f"all {self.gpu.max_slots} model slots busy")
        limit = self._budget.get(tenant)
        if limit is not None and self.used(tenant) + estimated_tokens > limit:
            return Decision(
                False,
                f"{tenant} would exceed its daily budget "
                f"({self.used(tenant)} + {estimated_tokens} > {limit})",
            )
        self._in_flight += 1
        self._used[tenant] = self.used(tenant) + estimated_tokens
        return ADMITTED

    def release(self) -> None:
        if self._in_flight == 0:
            raise RuntimeError("released more generations than were admitted")
        self._in_flight -= 1
