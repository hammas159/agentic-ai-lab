"""ledger-brain.

SME back office: invoices in, bank statements in, reconciliation, inventory and cash flow out.

The deterministic core lives in :mod:`ledger.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
