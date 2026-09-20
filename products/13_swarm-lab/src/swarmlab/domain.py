"""The two metrics that only exist because agents share a bus and a store.

Success rate and token cost can be measured with a for-loop. Duplicate calls
and conflicting writes cannot, and they are what actually degrade as N grows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    agent: str
    tool: str
    args: dict
    seq: int

    @property
    def signature(self) -> str:
        """Normalised arguments.

        Two agents fetching one URL with the parameters in a different order
        made the same call. Comparing the rendered call text says otherwise.
        """
        return self.tool + "|" + json.dumps(self.args, sort_keys=True, default=str)


@dataclass(frozen=True)
class Write:
    agent: str
    entity: str
    field_name: str
    value: object
    seq: int

    @property
    def slot(self) -> tuple[str, str]:
        return (self.entity, self.field_name)


@dataclass(frozen=True)
class Conflict:
    entity: str
    field_name: str
    agents: tuple[str, ...]
    values: tuple[object, ...]


def duplicate_calls(calls: list[ToolCall]) -> int:
    """Calls beyond the first for each distinct signature. Pure waste."""
    seen: set[str] = set()
    duplicates = 0
    for call in sorted(calls, key=lambda c: c.seq):
        if call.signature in seen:
            duplicates += 1
        else:
            seen.add(call.signature)
    return duplicates


def conflicting_writes(writes: list[Write]) -> list[Conflict]:
    """Two or more agents writing *different* values to one field.

    Two agents writing the same value is contention, not conflict. Counting it
    as conflict inflates the number exactly where the study is interesting.
    """
    slots: dict[tuple[str, str], list[Write]] = {}
    for write_ in sorted(writes, key=lambda w: w.seq):
        slots.setdefault(write_.slot, []).append(write_)

    out: list[Conflict] = []
    for (entity, field_name), group in sorted(slots.items()):
        agents = {w.agent for w in group}
        values = {json.dumps(w.value, sort_keys=True, default=str) for w in group}
        if len(agents) > 1 and len(values) > 1:
            out.append(
                Conflict(
                    entity=entity,
                    field_name=field_name,
                    agents=tuple(sorted(agents)),
                    values=tuple(w.value for w in group),
                )
            )
    return out


@dataclass
class Cell:
    """One (N, topology) cell of the sweep, across its repeats."""

    n_agents: int
    topology: str
    successes: list[bool] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n_agents < 1:
            raise ValueError("a cell needs at least one agent")
        if self.topology not in ("flat", "hierarchical"):
            raise ValueError("topology must be flat or hierarchical")

    @property
    def repeats(self) -> int:
        return len(self.successes)

    @property
    def success_rate(self) -> float:
        if not self.successes:
            raise ValueError("no repeats recorded for this cell")
        return sum(self.successes) / len(self.successes)

    @property
    def mean_tokens(self) -> float:
        if not self.tokens:
            raise ValueError("no token counts recorded for this cell")
        return sum(self.tokens) / len(self.tokens)

    @property
    def reportable(self) -> bool:
        """Three repeats minimum. One run is not a rate."""
        return self.repeats >= 3


def turning_point(cells: list[Cell]) -> int | None:
    """The smallest N whose success rate is below the previous N's.

    Returns None when success never falls, which is also a publishable result.
    """
    ordered = sorted((c for c in cells if c.reportable), key=lambda c: c.n_agents)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current.success_rate < previous.success_rate:
            return current.n_agents
    return None
