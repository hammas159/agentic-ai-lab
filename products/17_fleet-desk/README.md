# 17 · fleet-desk

> Dispatch and last mile: orders clustered, routes solved, exceptions handled, drivers spoken to in their own language.

**Status:** runs end to end. Intake is accepted onto the bus and returns; a worker drains
it; the graph pauses for a person; approving resumes it without regenerating anything. It
serves the shared operator console at `/`.

## The finding

**Measured on TSPLIB berlin52** — 52 real locations in Berlin, the standard routing
benchmark, against its **proven optimal tour**.

| Route | Length | Excess over optimal |
|---|---:|---:|
| Proven optimal | 7,542 | — |
| Nearest neighbour | 8,980 | 19.1% |
| **Angular sweep** — "go round the city in a circle" | **14,497** | **92.2%** |
| Visit stops in listed order | 22,205 | 194.4% |

**The most plausible thing a model can actually reason about is 92% worse than optimal.**

That middle row is the honest test of "do not let a language model plan a route". Comparing
against a model that outputs stops in the order it read them is a straw man; "go round the
city in a circle" is a genuinely sensible idea, it is the kind of spatial reasoning a model
can do without a distance matrix, and on real coordinates it very nearly doubles the
distance driven.

Even a proper greedy heuristic is 19% worse than optimal — **and it swings 26% on the
starting stop alone**, with the algorithm unchanged:

| Nearest neighbour over all 52 starting stops | |
|---|---:|
| Best | 8,181 (8.5% excess) |
| Median | 9,297 (23.3%) |
| Worst | 10,298 (36.5%) |

So the model narrates exceptions and writes to drivers, and the solver plans. Any proposed
route — whatever produced it — is scored on the same matrix, which is what `compare()` is
for.

### What proves the arithmetic

The optimal tour length computed here from raw coordinates is **7,542**, which is berlin52's
published optimum exactly. That match is the test that the EUC_2D rounding rule is right:
using unrounded distances gives a number close enough to look correct and wrong enough to
disagree with every published figure for this instance.

Reproduce it:

```bash
cd 17_fleet-desk && python -m pytest tests/test_real_routing.py -q     # 10 passed
```

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

## Running it

```bash
cd 17_fleet-desk
python -m pytest -q                      # 18 passed
PYTHONPATH="src;../platform/src" python -m fleetdesk.app    # console on http://127.0.0.1:8000
```

`app.py` picks a model by capability rather than by tag — `models.resolve("general", …)`
returns the best one installed and records which it was, so a later run on a larger model
is a comparison row rather than an overwrite. The tests never reach a real model:
`llm.Recorded` raises on any prompt it was not scripted for.

## The graph

Seven nodes, built from `agentplatform.blueprint.review_pipeline`. The same seven every
product has; what differs is the judgement at each step, which lives in `agents.py`.

```
triage ──(early exit)──► exit ──► END
   │
   └─► gather (fan-out) ──► synthesise ──► compose ──► gate ──► approve ──► commit ──► END
        [alpha, beta]          [model]      [model]            [pauses]
```

`triage`, the early exit and `commit` are rules. Two nodes call the model. The gate drops
anything the model wrote that no tool receipt supports, before a person ever sees it.

## What it does NOT do

- **It does not let the model plan a route.** The model narrates exceptions and writes to drivers.
- **It does not cancel a delivery.** Exceptions are classified and escalated.
- **It does not send a driver message unattended.**
- **It does not invent a distance.** A pair missing from the matrix is an error, not a straight line.

## Problems hit while building this

- The first cost function silently treated a missing matrix entry as zero, which made an invalid route look like the best one. Missing pairs raise.
- A route has to be validated as a permutation returning to the depot before it is costed; otherwise a route that skips two stops wins every comparison.

## Input / Output

Captured from a real run of this product — `scripts/capture.py` submits the payload below
through the HTTP surface, drains the queue, and approves. Every figure here came off a
machine.

**In** — `POST /intake`, keys: `challenger_route`, `claims`, `depot`, `issued_receipts`, `matrix`, `solver_route`, `stops`

Published to `fleet.tasks`; the call returns `202 {"status": "pending"}` with queue lag
**1**. Nothing has touched the model at this point.

**Out** — after one worker pass:

| | |
|---|---|
| Status | `awaiting_approval`, paused at `approve` |
| Nodes visited | `triage` → `gather` → `synthesise` → `compose` → `gate` → `approve` |
| Model calls already spent | **2** |
| Claims kept by the gate | "Backed by a real receipt." |
| Claims dropped | "Asserted with nothing behind it." |
| Drop rate | 0.5 |

After `POST /approvals/{run}/approve`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `triage` → `gather` → `synthesise` → `compose` → `gate` → `approve` → `commit` |
| Model calls | **2** — resuming added none |
| Result keys | `branch_status`, `branches`, `branches_failed`, `challenger_cost`, `challenger_route`, `claims`, `depot`, `dispatched`, `draft`, `drop_rate`, `dropped_claims`, `eta_minutes`, `invalid_route`, `issued_receipts`, `kept_claims`, `matrix`, `message.draft`, `model`, `pct_worse`, `solver_cost`, `solver_route`, `stops`, `summary`, `summary_subject` |

**The early exit**, on a payload that trips `rejected_route`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `triage` → `exit` |
| Model calls | **0** |

That last row is the one worth keeping. The cheap refusal costs nothing at all — no
gather, no generation — which is the whole reason it sits before the fan-out.
