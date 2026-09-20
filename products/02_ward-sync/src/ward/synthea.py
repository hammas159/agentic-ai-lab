"""Reading Synthea patient records, and rebuilding medication state from events.

`products/data/synthea_csv.zip` is Synthea's published sample: openly available,
no credentialing, and realistic in the way that matters here — medications carry
a START and a STOP, so a drug discontinued mid-encounter is visible as an event
rather than as an absence.

That is the whole question this product exists for. A "current medication list"
built by asking which drugs were started, and never asking which were stopped,
names drugs the patient is no longer on. Reading the event stream is the fix,
and the size of the problem is measurable on real records.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
ARCHIVE = DATA / "synthea_csv.zip"


class RecordsMissingError(FileNotFoundError):
    """The Synthea sample is not on disk."""


@dataclass(frozen=True)
class Medication:
    patient: str
    encounter: str
    code: str
    description: str
    start: str
    stop: str

    @property
    def stopped(self) -> bool:
        return bool(self.stop.strip())

    @property
    def same_day(self) -> bool:
        """Started and stopped on the same date — a single administration."""
        return self.stopped and self.start[:10] == self.stop[:10]


@dataclass(frozen=True)
class Encounter:
    id: str
    patient: str
    start: str
    stop: str
    description: str


def _rows(name: str, archive: Path):
    with zipfile.ZipFile(archive) as zf:
        match = next((n for n in zf.namelist() if n.endswith(name)), None)
        if match is None:
            raise RecordsMissingError(f"{name} not in {archive}")
        with zf.open(match) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))


@lru_cache(maxsize=1)
def medications(archive: str | None = None) -> tuple[Medication, ...]:
    path = Path(archive) if archive else ARCHIVE
    if not path.exists():
        raise RecordsMissingError(f"{path} is missing. Fetch Synthea's published sample.")
    return tuple(
        Medication(
            patient=r["PATIENT"],
            encounter=r["ENCOUNTER"],
            code=r["CODE"],
            description=r["DESCRIPTION"],
            start=r["START"],
            stop=r["STOP"],
        )
        for r in _rows("medications.csv", path)
    )


@lru_cache(maxsize=1)
def encounters(archive: str | None = None) -> dict[str, Encounter]:
    path = Path(archive) if archive else ARCHIVE
    if not path.exists():
        raise RecordsMissingError(f"{path} is missing.")
    return {
        r["Id"]: Encounter(
            id=r["Id"],
            patient=r["PATIENT"],
            start=r["START"],
            stop=r["STOP"],
            description=r.get("DESCRIPTION", ""),
        )
        for r in _rows("encounters.csv", path)
    }


def by_patient(archive: str | None = None) -> dict[str, list[Medication]]:
    out: dict[str, list[Medication]] = defaultdict(list)
    for med in medications(archive):
        out[med.patient].append(med)
    return dict(out)


@dataclass(frozen=True)
class Discrepancy:
    """One patient, and what each way of answering would have said."""

    patient: str
    started: int
    still_active: int
    discontinued: int

    @property
    def would_name_a_stopped_drug(self) -> bool:
        return self.discontinued > 0

    @property
    def overstatement(self) -> float:
        """How much longer the naive list is than the true one."""
        if self.still_active == 0:
            return float(self.discontinued)
        return self.discontinued / self.still_active


def discrepancies(archive: str | None = None) -> list[Discrepancy]:
    """Per patient: naive "everything started" against "still in force".

    The naive list is what you get from a medications table without reading the
    STOP column, which is exactly what a summary agent handed a "current
    medication list" is working from.
    """
    out: list[Discrepancy] = []
    for patient, meds in by_patient(archive).items():
        started = len(meds)
        discontinued = sum(1 for m in meds if m.stopped)
        out.append(
            Discrepancy(
                patient=patient,
                started=started,
                still_active=started - discontinued,
                discontinued=discontinued,
            )
        )
    return out
