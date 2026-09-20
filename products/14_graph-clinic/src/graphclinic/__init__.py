"""graph-clinic.

Clinical evidence assistant over a knowledge graph, where every answer carries the path it
came from.

The deterministic core lives in :mod:`graphclinic.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
