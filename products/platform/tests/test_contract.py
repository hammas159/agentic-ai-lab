"""One set of assertions, run against the in-memory ports and against the real ones.

The real implementations are skipped when the service is not up, so this file is
green on a laptop with nothing running and meaningful on a machine with
``docker compose up``. A contract test that only ever runs against a fake is a
test of the fake.
"""

from __future__ import annotations

import os

import pytest

from agentplatform.adapters import KafkaBus, PostgresStore, RedisCache
from agentplatform.ports import InMemoryBus, InMemoryCache, InMemoryStore

KAFKA = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
REDIS = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
POSTGRES = os.environ.get("POSTGRES_DSN", "postgresql://agent:agent@127.0.0.1:5432/agent")


def _topic(name: str) -> str:
    return f"contract-{name}-{os.getpid()}"


# ------------------------------------------------------------------ cache


def caches():
    yield pytest.param(InMemoryCache(), id="in-memory")
    real = RedisCache(REDIS)
    yield pytest.param(
        real,
        id="redis",
        marks=pytest.mark.skipif(not real.ping(), reason="no redis on " + REDIS),
    )


@pytest.fixture(params=list(caches()))
def cache(request):
    return request.param


def test_a_value_survives_a_round_trip(cache):
    cache.set("contract:v", "1")
    assert cache.get("contract:v") == "1"
    cache.delete("contract:v")


def test_a_missing_key_is_none_not_an_error(cache):
    assert cache.get("contract:absent") is None


def test_add_is_the_lock_primitive(cache):
    cache.delete("contract:lock")
    assert cache.add("contract:lock", "worker-a", 60) is True
    assert cache.add("contract:lock", "worker-b", 60) is False
    cache.delete("contract:lock")
    assert cache.add("contract:lock", "worker-b", 60) is True
    cache.delete("contract:lock")


# ------------------------------------------------------------------ store


def stores():
    yield pytest.param(InMemoryStore(), id="in-memory")
    real = PostgresStore(POSTGRES)
    yield pytest.param(
        real,
        id="postgres",
        marks=pytest.mark.skipif(not real.reachable(), reason="no postgres"),
    )


@pytest.fixture(params=list(stores()))
def store(request):
    return request.param


def test_a_row_survives_a_round_trip(store):
    store.put("contract", "r1", {"status": "done", "n": 2})
    assert store.get("contract", "r1") == {"status": "done", "n": 2}


def test_a_put_replaces_rather_than_duplicating(store):
    store.put("contract", "r2", {"n": 1})
    store.put("contract", "r2", {"n": 2})
    assert store.get("contract", "r2") == {"n": 2}
    assert len([r for r in store.rows("contract") if r.get("n") == 2]) >= 1


def test_a_missing_row_is_none(store):
    assert store.get("contract", "never-written") is None


# ------------------------------------------------------------------ bus


def buses():
    yield pytest.param(InMemoryBus(), id="in-memory")
    real = KafkaBus(KAFKA)
    yield pytest.param(
        real,
        id="kafka",
        marks=pytest.mark.skipif(not real.reachable(), reason="no broker on " + KAFKA),
    )


@pytest.fixture(params=list(buses()))
def bus(request):
    return request.param


def test_messages_for_one_key_arrive_in_order(bus):
    topic = _topic("order")
    for n in range(5):
        bus.publish(topic, "deal:4192", {"n": n})
    got = bus.poll(topic, "contract-workers", limit=10)
    assert [m.value["n"] for m in got] == [0, 1, 2, 3, 4]


def test_one_key_always_lands_on_one_partition(bus):
    topic = _topic("partition")
    first = bus.publish(topic, "deal:4192", {"n": 1})
    second = bus.publish(topic, "deal:4192", {"n": 2})
    assert first.partition == second.partition


def test_two_groups_read_the_same_topic_independently(bus):
    topic = _topic("groups")
    bus.publish(topic, "deal:1", {"n": 1})
    assert len(bus.poll(topic, "contract-a", limit=10)) == 1
    assert len(bus.poll(topic, "contract-b", limit=10)) == 1
