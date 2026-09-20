"""The OFAC sanctions list, and the ground truth hiding inside it.

`SDN.CSV` carries one primary name per entity. `ALT.CSV` carries that entity's
known aliases, joined on the entity number. So every (primary, alias) pair is a
labelled positive: two spellings that a sanctions authority has already declared
to be the same party.

That is a rare thing — a name-matching benchmark with real labels, on exactly the
Arabic- and Urdu-origin names this product exists for, and no annotation
required. Non-matching pairs across different entity numbers are the negatives.

Files are OFAC's published exports, committed under `products/data/`.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
SDN = DATA / "ofac_sdn.csv"
ALT = DATA / "ofac_alt.csv"

NULL = "-0-"

# SDN.CSV has no header row; these are the published column positions.
SDN_ENT, SDN_NAME, SDN_TYPE, SDN_PROGRAM = 0, 1, 2, 3
ALT_ENT, ALT_TYPE, ALT_NAME = 0, 2, 3

INDIVIDUAL = "individual"


class ListsMissingError(FileNotFoundError):
    """The OFAC exports are not on disk."""


@dataclass
class Entity:
    ent_num: str
    primary: str
    kind: str
    programs: str
    aliases: list[str] = field(default_factory=list)

    @property
    def is_individual(self) -> bool:
        return self.kind.strip().lower() == INDIVIDUAL

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """Labelled positives: every alias against the primary name."""
        return [(self.primary, a) for a in self.aliases]


def _clean(value: str) -> str:
    value = value.strip()
    return "" if value == NULL else value


@lru_cache(maxsize=1)
def load(sdn: str | None = None, alt: str | None = None) -> tuple[Entity, ...]:
    """Every sanctioned entity with its aliases attached."""
    sdn_path = Path(sdn) if sdn else SDN
    alt_path = Path(alt) if alt else ALT
    for path in (sdn_path, alt_path):
        if not path.exists():
            raise ListsMissingError(
                f"{path} is missing. Fetch OFAC's published exports into products/data/."
            )

    by_ent: dict[str, Entity] = {}
    with sdn_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) <= SDN_PROGRAM:
                continue
            name = _clean(row[SDN_NAME])
            if not name:
                continue
            ent = _clean(row[SDN_ENT])
            by_ent[ent] = Entity(
                ent_num=ent,
                primary=name,
                kind=_clean(row[SDN_TYPE]),
                programs=_clean(row[SDN_PROGRAM]),
            )

    aliases: dict[str, list[str]] = defaultdict(list)
    with alt_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) <= ALT_NAME:
                continue
            name = _clean(row[ALT_NAME])
            if name:
                aliases[_clean(row[ALT_ENT])].append(name)

    for ent, names in aliases.items():
        if ent in by_ent:
            by_ent[ent].aliases = names

    return tuple(by_ent.values())


def individuals(**kw) -> list[Entity]:
    """People only. Vessels and companies match by different rules."""
    return [e for e in load(**kw) if e.is_individual]


def labelled_pairs(only_individuals: bool = True, **kw) -> list[tuple[str, str]]:
    """Every (primary, alias) pair OFAC itself says is one party."""
    source = individuals(**kw) if only_individuals else list(load(**kw))
    return [pair for e in source for pair in e.pairs]


def names(only_individuals: bool = True, **kw) -> list[str]:
    source = individuals(**kw) if only_individuals else list(load(**kw))
    return [e.primary for e in source]
