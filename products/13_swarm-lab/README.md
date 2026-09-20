# 13 · swarm-lab

> A scaling observatory: what actually happens to a multi-agent system as N grows.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** the priority-80 item from the SWE queue, where it is described as the strongest unbuilt idea.

## The finding it exists to produce

Sweep N = 1, 2, 3, 5, 8, 13, 21, 34, flat against hierarchical, model held constant, at
least three repeats per cell. Log success, tokens, wall clock, tool calls, **duplicate calls
and conflicting writes**. The shape of the answer is *"beyond N = X, adding agents cut task
success by Y% while tripling token cost"*, and almost nobody publishes that curve.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `sweep-runner` | `trials` — the harness, deterministic | interpreting a result |
| `worker` | its own `tool_calls` and `writes` | another worker's entity |
| `collector` | `metrics` — counted, never estimated | a metric it did not count |
| `narrator` | `reports.draft` | a number absent from `metrics` |

## Architecture

| Topic | Carries |
|---|---|
| `swarm.intake` | everything arriving from outside |
| `swarm.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `swarm.events` | the audit trail, and what the projector and SSE stream read |
| `swarm.approvals` | an agent needs a person; resumes a checkpointed graph |
| `swarm.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:entity:{id}` | the contention this study exists to measure |
| `budget:{trial}` | a runaway sweep must not eat a day |
| `live:sweep` | progress for the page |
| `idem:trial:{n}:{repeat}` | a resumed sweep must not double-count |

**Postgres:** `sweeps, trials, tool_calls, writes, metrics, reports, events`.

**UI:** Observable Framework — one page per sweep, with the curve as the artefact.

## Real data

The infrastructure already exists: `mcp-lab`, `bounded-agent-runtime`, `enterprise-ops-crew`, `langgraph-lab`. Zero downloads. The failure mode has already happened here for real — a broad `taskkill` killed sibling agents' live runs — which is why `powerguard`'s ownership rule and this study's conflict metric are the same idea.

## The deterministic core

`src/swarmlab/domain.py` decides duplicate tool calls and conflicting writes — the two metrics that only exist because there is a bus and a shared store. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not claim a framework is better.** The model and the task are held constant; N is the variable.
- **It does not report a single run.** At least three repeats per cell, and the spread is reported.
- **It does not estimate a token count.** Counted from the trace.
- **It does not build a swarm as a product.** Building it is not the valuable part; measuring it is.

## Problems hit while building this

- Duplicate detection needs the *arguments* normalised, not the call text. Two agents fetching the same URL with the parameters in a different order are one duplicate, and a string comparison says they are two distinct calls.
- A conflicting write is not simply two writes to one field. Two agents writing the same value is contention, not conflict, and counting it as conflict inflates the headline exactly where the study is most interesting.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
