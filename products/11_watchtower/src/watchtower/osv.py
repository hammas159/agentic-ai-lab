"""The OSV vulnerability database, and the range logic a naive matcher skips.

`products/data/osv_pypi.zip` is OSV's published export for PyPI — 25,645 real
advisories, each carrying the version ranges it applies to.

That structure is the point. An advisory does not say "fixed in X"; it says
"introduced at A, fixed at B; introduced again at C, fixed at D". A package can
sit *after* one fix and *before* the next, or after all of them. Comparing an
installed version against the highest fixed version and calling anything below
it vulnerable is the shortcut every quick scanner takes, and it is wrong in both
directions.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
OSV_ZIP = DATA / "osv_pypi.zip"

_NUM = re.compile(r"\d+")


class DatabaseMissingError(FileNotFoundError):
    """The OSV export is not on disk."""


def version_key(version: str) -> tuple[int, ...]:
    """A comparable tuple from a PEP 440-ish version string.

    Deliberately not a full PEP 440 implementation: this needs an ordering, and
    the parts that differ between a full parser and this one (pre-release
    ordering, local versions) do not change which side of a range a release
    falls on for the overwhelming majority of advisories. Where it would, the
    honest answer is that this is approximate, and it is said here rather than
    implied to be exact.
    """
    parts = tuple(int(n) for n in _NUM.findall(version.split("+")[0])[:4])
    return parts or (0,)


@dataclass(frozen=True)
class Window:
    """One introduced -> fixed interval. ``fixed`` of None means still open."""

    introduced: str
    fixed: str | None

    def covers(self, version: str) -> bool:
        v = version_key(version)
        if v < version_key(self.introduced):
            return False
        return self.fixed is None or v < version_key(self.fixed)


@dataclass
class Advisory:
    id: str
    package: str
    summary: str
    windows: list[Window] = field(default_factory=list)
    explicit: set[str] = field(default_factory=set)

    @property
    def highest_fixed(self) -> str | None:
        fixes = [w.fixed for w in self.windows if w.fixed]
        return max(fixes, key=version_key) if fixes else None

    def affects(self, version: str) -> bool:
        """Correct answer: is this version inside any affected window."""
        if version in self.explicit:
            return True
        return any(w.covers(version) for w in self.windows)

    def affects_naively(self, version: str) -> bool:
        """The shortcut: anything below the highest fixed version is vulnerable.

        No notion of when the problem was introduced, and no notion of a version
        that sits between two windows.
        """
        top = self.highest_fixed
        return top is not None and version_key(version) < version_key(top)


def _advisories_from(raw: dict) -> list[Advisory]:
    out: list[Advisory] = []
    for affected in raw.get("affected", []):
        package = (affected.get("package") or {}).get("name", "")
        if not package:
            continue
        adv = Advisory(
            id=raw.get("id", ""),
            package=package.lower().replace("_", "-"),
            summary=raw.get("summary", ""),
            explicit=set(affected.get("versions", []) or []),
        )
        for rng in affected.get("ranges", []) or []:
            introduced = None
            for event in rng.get("events", []):
                if "introduced" in event:
                    introduced = event["introduced"]
                elif "fixed" in event and introduced is not None:
                    adv.windows.append(Window(introduced, event["fixed"]))
                    introduced = None
                elif "last_affected" in event and introduced is not None:
                    adv.windows.append(Window(introduced, None))
                    introduced = None
            if introduced is not None:
                adv.windows.append(Window(introduced, None))
        if adv.windows or adv.explicit:
            out.append(adv)
    return out


@lru_cache(maxsize=1)
def load(path: str | None = None) -> dict:
    """Advisories indexed by normalised package name."""
    target = Path(path) if path else OSV_ZIP
    if not target.exists():
        raise DatabaseMissingError(f"{target} is missing. Fetch OSV's PyPI export.")

    index: dict[str, list[Advisory]] = {}
    with zipfile.ZipFile(target) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            try:
                raw = json.loads(zf.read(name))
            except (json.JSONDecodeError, KeyError):
                continue
            if raw.get("withdrawn"):
                continue
            for adv in _advisories_from(raw):
                index.setdefault(adv.package, []).append(adv)
    return index


def installed(python_executable: str | None = None) -> dict[str, str]:
    """Real packages in an environment, name -> version."""
    import importlib.metadata as md  # noqa: PLC0415

    out: dict[str, str] = {}
    for dist in md.distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name:
            out[name] = dist.version
    return out
