"""ward-sync.

Hospital operations agents: intake, bed and theatre assignment, result routing, discharge,
pre-authorisation.

The deterministic core lives in :mod:`ward.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
