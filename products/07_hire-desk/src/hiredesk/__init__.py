"""hire-desk.

CV parsing, blind scoring against a fixed rubric, an interview kit, and a fairness audit
that runs continuously.

The deterministic core lives in :mod:`hiredesk.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
