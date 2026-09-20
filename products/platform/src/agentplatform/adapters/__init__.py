"""Bindings from the ports to the real thing.

Each adapter imports its client lazily, so importing this package costs nothing
and the platform still runs with none of them installed. The contract tests in
``tests/test_contract.py`` run the same assertions against the in-memory
implementations and against these, and skip the real ones when the service is
not reachable.
"""

from .kafka_bus import KafkaBus
from .postgres_store import PostgresStore
from .redis_cache import RedisCache

__all__ = ["KafkaBus", "PostgresStore", "RedisCache"]
