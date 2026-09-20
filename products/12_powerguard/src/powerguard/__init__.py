"""powerguard.

Machine custodian: on mains loss, checkpoint the training run, pause the downloads, sleep
the displays, hibernate before the battery goes.

The deterministic core lives in :mod:`powerguard.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
