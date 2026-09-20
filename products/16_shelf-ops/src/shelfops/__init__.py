"""shelf-ops.

Marketplace operations: catalogue, repricing, promotions, returns triage and supplier
chasing, with one price authority.

The deterministic core lives in :mod:`shelfops.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
