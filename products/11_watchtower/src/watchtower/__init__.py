"""watchtower.

Vulnerability, exposure and configuration-drift agent for the machines you are authorised to
scan.

The deterministic core lives in :mod:`watchtower.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
