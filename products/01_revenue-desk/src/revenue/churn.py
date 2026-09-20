"""Measuring reverts in real edit history.

This product's finding is how often one writer's update destroys another's
recent correction. A CRM with agents writing into it is the setting; the
mechanism is general, and there is a large, real, dated corpus of exactly that
mechanism on this machine: the git history of thirty-odd repositories.

A revert here is a line that went A, then B, then back to A. That is not churn
and not a rewrite — it is one edit undoing another, which is precisely the event
`domain.detect_reverts` looks for on a deal record.

Reading real history rather than inventing a CRM log means the rate is a
property of how editing actually goes, not of how a fixture was written.
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPOS = Path("D:/github")


class NoHistoryError(RuntimeError):
    """The repository has no readable history."""


@dataclass(frozen=True)
class Edit:
    """One change to one line of one file."""

    commit: str
    seq: int
    path: str
    line: str
    added: bool


@dataclass
class Revert:
    path: str
    line: str
    first_seen: int
    removed_at: int
    restored_at: int

    @property
    def gap(self) -> int:
        """Commits between the removal and the restoration."""
        return self.restored_at - self.removed_at


@dataclass
class Summary:
    repo: str
    commits: int = 0
    edits: int = 0
    reverts: list = field(default_factory=list)

    @property
    def revert_rate(self) -> float:
        return len(self.reverts) / self.edits if self.edits else 0.0


def _git(repo: Path, *args: str, timeout: float = 180.0) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NoHistoryError(f"{repo}: {exc}") from exc
    return proc.stdout


def edits(repo: Path, limit: int = 200) -> list[Edit]:
    """Line-level additions and removals, oldest commit first.

    Whitespace-only and pure-move changes are excluded by asking git to ignore
    them: a line reindented is not a correction being undone.
    """
    raw = _git(
        repo,
        "log",
        "--reverse",
        f"-n{limit}",
        "--format=__commit__ %h",
        "-U0",
        "--no-renames",
        "-w",
        "--ignore-blank-lines",
        "-p",
    )
    if not raw.strip():
        raise NoHistoryError(f"{repo} has no history")

    out: list[Edit] = []
    commit = ""
    path = ""
    seq = -1
    for line in raw.splitlines():
        if line.startswith("__commit__ "):
            commit = line.split(" ", 1)[1].strip()
            seq += 1
        elif line.startswith("+++ b/"):
            path = line[6:].strip()
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            body = line[1:].strip()
            if len(body) < 8:
                continue  # a brace or a comma is not a correction
            out.append(Edit(commit, seq, path, body, added=line.startswith("+")))
    return out


MIN_MEANINGFUL = 8


def find_reverts(history: list[Edit]) -> list[Revert]:
    """Lines that were removed and later restored verbatim.

    Keyed on (file, exact line). Requiring the text to come back identically is
    strict on purpose: anything looser measures rewriting rather than undoing.

    Trivially short lines are skipped here rather than only at parse time. A
    closing brace reappearing is not a judgement being undone, and that is a
    property of what counts as a revert — it should hold for any caller, not
    only for edits this module happened to read out of git.
    """
    state: dict[tuple[str, str], list[tuple[int, bool]]] = defaultdict(list)
    for edit in history:
        if len(edit.line.strip()) < MIN_MEANINGFUL:
            continue
        state[(edit.path, edit.line)].append((edit.seq, edit.added))

    found: list[Revert] = []
    for (path, line), events in state.items():
        events.sort()
        first = None
        removed = None
        for seq, added in events:
            if added and first is None:
                first = seq
            elif not added and first is not None and removed is None:
                removed = seq
            elif added and removed is not None:
                found.append(Revert(path, line, first, removed, seq))
                removed = None
    return found


@lru_cache(maxsize=1)
def survey(root: str | None = None, repos: int = 12, limit: int = 200) -> tuple[Summary, ...]:
    """Every repository under ``root`` with history, summarised."""
    base = Path(root) if root else REPOS
    out: list[Summary] = []
    for path in sorted(p for p in base.iterdir() if p.is_dir()):
        if path.name.startswith((".", "_")) or not (path / ".git").exists():
            continue
        try:
            history = edits(path, limit=limit)
        except NoHistoryError:
            continue
        if not history:
            continue
        out.append(
            Summary(
                repo=path.name,
                commits=len({e.commit for e in history}),
                edits=len(history),
                reverts=find_reverts(history),
            )
        )
        if len(out) >= repos:
            break
    return tuple(out)
