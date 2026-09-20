"""The real evidence sources for this product.

Not stubs. `surveillance` and `batches` both read
`products/data/clcuv.gb` — 532 KB of real Cotton leaf curl virus records
downloaded from NCBI GenBank, 60 genomes across Pakistan, India and China.

Each branch returns receipt ids that are real accessions, so the grounding gate
is checking claims against evidence that actually exists rather than against a
list this module invented.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .domain import Isolate, collapse_clonal
from .genbank import Record, read

DATA = Path(__file__).resolve().parents[3] / "data" / "clcuv.gb"


class CorpusMissingError(FileNotFoundError):
    """The surveillance corpus is not on disk. Said plainly, not worked around."""


@lru_cache(maxsize=1)
def corpus(path: str | None = None) -> tuple[Record, ...]:
    """Every usable record. Cached: the file does not change during a run."""
    target = Path(path) if path else DATA
    if not target.exists():
        raise CorpusMissingError(
            f"{target} is missing. It is a copy of "
            "clcuv-surveillance/data/clcuv.gb, committed for offline reproduction."
        )
    return tuple(r for r in read(target) if r.sequence)


def isolates(path: str | None = None) -> list[Isolate]:
    """The corpus in the shape the surveillance core takes."""
    return [Isolate(r.accession, r.sequence, r.site, r.day) for r in corpus(path)]


def surveillance(state: dict) -> list[str]:
    """Accessions backing the variants this report is about.

    Returns one accession per *collapsed cluster*, not per record. Returning all
    sixty would hand the gate sixty receipts for forty-one observations, which
    is the same double-counting the product exists to catch — in the evidence
    list this time rather than in the statistics.
    """
    clusters = collapse_clonal(isolates(state.get("corpus")))
    return sorted(c.members[0].id for c in clusters)


def batches(state: dict) -> list[str]:
    """Submission batches present in the corpus.

    A batch is the unit a field is sampled in. ``CLCMV/S2-1`` .. ``S2-8`` is
    eight genomes from one submission, and treating those as eight independent
    observations is exactly how nine variants once looked like they were
    emerging.
    """
    return sorted({r.submission for r in corpus(state.get("corpus"))})


def default_sources() -> dict:
    """The fan-out. Both branches read the real corpus."""
    return {"surveillance": surveillance, "batches": batches}
