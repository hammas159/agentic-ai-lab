"""driftwatch.

Watches a repository for the moment its documentation stops being true, and opens the pull
request that fixes it.

The deterministic core lives in :mod:`driftwatch.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
