# 17 · fleet-desk

> Dispatch and last mile: orders clustered, routes solved, exceptions handled, drivers spoken to in their own language.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Let the model re-plan a route and measure it against the solver, on real distances. It will
be worse; quantify by how much. The useful version of 'do not let an LLM do optimisation'
is a number on your own order book, not an assertion.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `order-intake` | `orders`, `stops` | a route |
| `route-planner` | `routes` — solver output only | a route it did not cost |
| `exception-triager` | `exceptions.kind` | cancelling a delivery |
| `driver-comms` | `messages.draft` (Urdu and English) | sending without a dispatcher |
| `eta-communicator` | `etas` — computed from the route | an ETA it did not compute |

## Architecture

| Topic | Carries |
|---|---|
| `fleet.intake` | everything arriving from outside |
| `fleet.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `fleet.events` | the audit trail, and what the projector and SSE stream read |
| `fleet.approvals` | an agent needs a person; resumes a checkpointed graph |
| `fleet.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:route:{id}` | a route being edited by two dispatchers is a lost parcel |
| `live:positions` | driver positions, read constantly and stored rarely |
| `cache:matrix:{hash}` | a distance matrix is expensive and reusable |
| `idem:order:{reference}` | orders arrive by API and by CSV |

**Postgres:** `orders, stops, vehicles, routes, legs, exceptions, proofs, events`.

**UI:** MapLibre GL, map first — a dispatcher does not read a table.

## Real data

OpenStreetMap road distances for a real city, and a generated order book whose *geography* is real even when the customers are not. The measurement only needs the distances to be true.

## The deterministic core

`src/fleetdesk/domain.py` decides what a route actually costs, so any proposed route — solver or model — can be scored on the same matrix. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not let the model plan a route.** The model narrates exceptions and writes to drivers.
- **It does not cancel a delivery.** Exceptions are classified and escalated.
- **It does not send a driver message unattended.**
- **It does not invent a distance.** A pair missing from the matrix is an error, not a straight line.

## Problems hit while building this

- The first cost function silently treated a missing matrix entry as zero, which made an invalid route look like the best one. Missing pairs raise.
- A route has to be validated as a permutation returning to the depot before it is costed; otherwise a route that skips two stops wins every comparison.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
