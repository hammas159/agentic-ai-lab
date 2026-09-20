import pytest

from agentplatform import api, graphs
from agentplatform.graphs import END, Graph, Node
from agentplatform.ports import InMemoryBus, InMemoryStore

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def graph(calls=None):
    calls = calls if calls is not None else []
    return Graph(
        nodes={
            "draft": Node(
                "draft", graphs.LLM, lambda s: calls.append("draft") or {"draft": "hi"}
            ),
            "approve": Node("approve", graphs.INTERRUPT),
            "send": Node("send", graphs.TOOL, lambda s: {"sent": True}),
        },
        entry="draft",
        edges={"draft": "approve", "approve": "send", "send": END},
    )


def runtime(calls=None):
    return api.Runtime(
        domain="crm", bus=InMemoryBus(), store=InMemoryStore(), graph=graph(calls)
    )


def test_health_names_the_topics_and_the_lag():
    client = TestClient(api.create_app(runtime()))
    body = client.get("/health").json()
    assert body["topics"][0] == "crm.intake"
    assert body["lag"] == 0


def test_intake_returns_immediately_without_running_the_graph():
    calls = []
    rt = runtime(calls)
    client = TestClient(api.create_app(rt))
    response = client.post("/intake", json={"entity": "4192", "payload": {"x": 1}})
    assert response.status_code == 202
    assert response.json()["status"] == api.PENDING
    assert calls == []  # the GPU has not been touched
    assert rt.bus.lag("crm.tasks", rt.group) == 1


def test_intake_without_an_entity_is_refused():
    client = TestClient(api.create_app(runtime()))
    assert client.post("/intake", json={}).status_code == 422


def test_the_worker_drains_the_queue_and_the_run_pauses_for_approval():
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    assert rt.drain() == 1
    row = client.get("/runs/r1").json()
    assert row["status"] == api.AWAITING_APPROVAL
    assert row["awaiting"] == "approve"


def test_a_paused_run_already_reports_what_it_cost():
    # A run waiting for approval has already spent generations producing the
    # thing being approved. Reporting zero until it resumes makes the only
    # interesting cost invisible.
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    paused = client.get("/runs/r1").json()
    assert paused["llm_calls"] == 1
    assert paused["visited"] == ["draft", "approve"]

    done = client.post("/approvals/r1/approve").json()
    assert done["llm_calls"] == 1  # resuming added none
    # "approve" does not appear twice: resuming starts at the node *after* the
    # interrupt, so the pause itself is not re-entered either.
    assert done["visited"] == ["draft", "approve", "send"]


def test_the_approvals_queue_lists_what_is_waiting():
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    assert [r["run_id"] for r in client.get("/approvals").json()] == ["r1"]


def test_approving_resumes_without_regenerating():
    calls = []
    rt = runtime(calls)
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    assert calls == ["draft"]
    body = client.post("/approvals/r1/approve").json()
    assert body["status"] == api.DONE
    assert body["result"]["sent"] is True
    assert calls == ["draft"]


def test_rejecting_ends_the_run_with_a_reason():
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    body = client.post("/approvals/r1/reject", json={"reason": "wrong contact"}).json()
    assert body["status"] == api.FAILED
    assert body["reason"] == "wrong contact"


def test_approving_a_run_that_is_not_waiting_is_a_conflict():
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    client.post("/approvals/r1/approve")
    assert client.post("/approvals/r1/approve").status_code == 409


def test_an_unknown_run_is_a_404():
    client = TestClient(api.create_app(runtime()))
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/approvals/nope/approve").status_code == 404


def test_a_failing_node_sends_the_run_to_the_dead_letter_queue():
    def boom(state):
        raise RuntimeError("tool exploded")

    rt = api.Runtime(
        domain="crm",
        bus=InMemoryBus(),
        store=InMemoryStore(),
        graph=Graph(
            nodes={"a": Node("a", graphs.TOOL, boom)},
            entry="a",
            edges={"a": END},
        ),
    )
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    assert client.get("/runs/r1").json()["status"] == api.FAILED
    assert len(rt.bus.poll("crm.dlq", "humans")) == 1


def test_completion_is_announced_on_the_events_topic():
    rt = runtime()
    client = TestClient(api.create_app(rt))
    client.post("/intake", json={"run_id": "r1", "entity": "4192"})
    rt.drain()
    client.post("/approvals/r1/approve")
    events = rt.bus.poll("crm.events", "audit")
    assert [e.value["event"] for e in events] == ["completed"]
