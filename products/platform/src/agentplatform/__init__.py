"""Shared platform for the twenty products in ../.

Six pieces, none of which needs a broker, a database or a model to be correct:

- topics      the five-topic convention and stable partitioning
- keys        the six Redis keys, each with the TTL that makes it safe
- authority   which agent may write which field, default-deny
- gate        the grounding gate that drops a claim without a receipt
- admission   how many model workers this GPU can actually run
- memory      semantic memory whose writes are gated on contradiction
"""

__all__ = ["admission", "authority", "gate", "keys", "memory", "topics"]
