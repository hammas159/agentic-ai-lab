"""The LoCoMo long-term memory benchmark, and what a sliding window loses on it.

`products/data/locomo10.json` is LoCoMo: ten very long conversations — a median
of 29 sessions and 646 turns each — with 1,986 questions whose answers point at
the specific turns that support them.

Those evidence pointers are the useful part. They make "how far back does this
answer live" a measurement rather than an intuition, and therefore make "what
would a sliding window lose" a measurement too.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
BENCHMARK = DATA / "locomo10.json"

# Evidence ids look like "D1:3" — session 1, turn 3.
_EVIDENCE = re.compile(r"D(\d+):(\d+)")


class BenchmarkMissingError(FileNotFoundError):
    """The LoCoMo file is not on disk."""


@dataclass(frozen=True)
class Turn:
    session: int
    speaker: str
    dia_id: str
    text: str


@dataclass(frozen=True)
class Question:
    text: str
    answer: str
    category: int
    evidence: tuple[str, ...]
    sessions: int  # how many sessions the conversation has

    @property
    def evidence_sessions(self) -> tuple[int, ...]:
        found = [int(m.group(1)) for e in self.evidence if (m := _EVIDENCE.match(str(e)))]
        return tuple(sorted(set(found)))

    @property
    def resolvable(self) -> bool:
        return bool(self.evidence_sessions)

    @property
    def sessions_back(self) -> int:
        """How far back the EARLIEST supporting turn is.

        The earliest, not the latest: a question needing turns from sessions 3
        and 27 is unanswerable unless session 3 is still there.
        """
        return self.sessions - min(self.evidence_sessions)

    def answerable_within(self, window: int) -> bool:
        """Could a memory holding only the last ``window`` sessions answer this."""
        if window < 1:
            raise ValueError("a window holds at least one session")
        return self.sessions_back < window


@dataclass(frozen=True)
class Conversation:
    sample_id: str
    speakers: tuple[str, str]
    turns: tuple[Turn, ...]
    questions: tuple[Question, ...]

    @property
    def sessions(self) -> int:
        return max((t.session for t in self.turns), default=0)


def _session_keys(conversation: dict) -> list[tuple[int, str]]:
    out = []
    for key in conversation:
        if key.startswith("session_") and not key.endswith("date_time"):
            try:
                out.append((int(key.split("_")[1]), key))
            except (IndexError, ValueError):
                continue
    return sorted(out)


@lru_cache(maxsize=1)
def load(path: str | None = None) -> tuple[Conversation, ...]:
    target = Path(path) if path else BENCHMARK
    if not target.exists():
        raise BenchmarkMissingError(f"{target} is missing. Fetch LoCoMo's published sample.")
    raw = json.loads(target.read_text(encoding="utf-8"))

    out: list[Conversation] = []
    for sample in raw:
        conversation = sample.get("conversation", {})
        keys = _session_keys(conversation)
        turns = tuple(
            Turn(
                session=index,
                speaker=turn.get("speaker", ""),
                dia_id=turn.get("dia_id", ""),
                text=turn.get("text", ""),
            )
            for index, key in keys
            for turn in conversation.get(key, [])
        )
        total = len(keys)
        questions = tuple(
            Question(
                text=q.get("question", ""),
                answer=str(q.get("answer", "")),
                category=int(q.get("category", 0) or 0),
                evidence=tuple(q.get("evidence") or ()),
                sessions=total,
            )
            for q in sample.get("qa", [])
        )
        out.append(
            Conversation(
                sample_id=str(sample.get("sample_id", "")),
                speakers=(
                    conversation.get("speaker_a", ""),
                    conversation.get("speaker_b", ""),
                ),
                turns=turns,
                questions=questions,
            )
        )
    return tuple(out)


def questions(path: str | None = None) -> list[Question]:
    """Every question whose evidence resolves to a session."""
    return [q for c in load(path) for q in c.questions if q.resolvable]


def coverage(window: int, path: str | None = None) -> float:
    """Share of questions a memory of the last ``window`` sessions could answer."""
    qs = questions(path)
    if not qs:
        return 0.0
    return sum(1 for q in qs if q.answerable_within(window)) / len(qs)
