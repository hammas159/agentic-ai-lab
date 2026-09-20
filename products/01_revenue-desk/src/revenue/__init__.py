"""revenue-desk.

Multi-agent CRM and lead engine whose forecast is arithmetic and whose agents cannot
overwrite you.

The deterministic core lives in :mod:`revenue.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
