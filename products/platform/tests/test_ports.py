from agentplatform.ports import InMemoryBus, InMemoryCache, InMemoryStore


def test_one_key_always_lands_on_one_partition():
    bus = InMemoryBus()
    first = bus.publish("crm.tasks", "deal:4192", {"n": 1})
    second = bus.publish("crm.tasks", "deal:4192", {"n": 2})
    assert first.partition == second.partition
    assert (first.offset, second.offset) == (0, 1)


def test_messages_for_one_key_arrive_in_order():
    bus = InMemoryBus()
    for n in range(5):
        bus.publish("crm.tasks", "deal:4192", {"n": n})
    got = bus.poll("crm.tasks", "workers", limit=10)
    assert [m.value["n"] for m in got] == [0, 1, 2, 3, 4]


def test_polling_advances_the_group_cursor():
    bus = InMemoryBus()
    bus.publish("crm.tasks", "deal:1", {"n": 1})
    assert len(bus.poll("crm.tasks", "workers")) == 1
    assert bus.poll("crm.tasks", "workers") == []


def test_two_groups_read_the_same_topic_independently():
    bus = InMemoryBus()
    bus.publish("crm.events", "deal:1", {"n": 1})
    assert len(bus.poll("crm.events", "projector")) == 1
    assert len(bus.poll("crm.events", "audit")) == 1


def test_rewinding_replays_the_log():
    bus = InMemoryBus()
    bus.publish("crm.events", "deal:1", {"n": 1})
    bus.poll("crm.events", "audit")
    bus.rewind("crm.events", "audit")
    assert len(bus.poll("crm.events", "audit")) == 1


def test_lag_is_what_is_not_yet_consumed():
    bus = InMemoryBus()
    bus.publish("crm.tasks", "deal:1", {"n": 1})
    bus.publish("crm.tasks", "deal:2", {"n": 2})
    assert bus.lag("crm.tasks", "workers") == 2
    bus.poll("crm.tasks", "workers", limit=1)
    assert bus.lag("crm.tasks", "workers") == 1


def test_the_store_copies_rather_than_aliasing():
    store = InMemoryStore()
    row = {"a": 1}
    store.put("runs", "r1", row)
    row["a"] = 2
    assert store.get("runs", "r1") == {"a": 1}


def test_add_is_the_lock_primitive():
    cache = InMemoryCache()
    assert cache.add("lock:deal:1", "worker-a") is True
    assert cache.add("lock:deal:1", "worker-b") is False
    cache.delete("lock:deal:1")
    assert cache.add("lock:deal:1", "worker-b") is True
