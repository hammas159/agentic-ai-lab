# 14 · graph-clinic

> Clinical evidence assistant over a knowledge graph, where every answer carries the path it came from.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** the priority-68 Medical Graph RAG item from the SWE queue. Brings Neo4j, a database nothing else in the portfolio uses.

## The finding it exists to produce

Graph traversal against plain hybrid retrieval on the same questions. Given `rag-lab`'s
result — six of eight variants lost to a plain baseline, and HyDE lost to a technique from
1971 — the honest hypothesis is that this one loses too. Publishing that is worth more than
another win, and the path provenance is valuable whichever way the accuracy goes.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `ingester` | `documents` | an entity or a relation |
| `entity-linker` | `mentions` with a confidence and a span | a relation |
| `graph-builder` | `nodes`, `edges` — deterministic from linked mentions | an inferred edge |
| `traversal-planner` | `queries` | an unbounded walk |
| `synthesiser` | `answers.draft` with the path attached | an answer whose path is empty |
| `contradiction-reporter` | `contradictions` | choosing between two sources |

## Architecture

| Topic | Carries |
|---|---|
| `graph.intake` | everything arriving from outside |
| `graph.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `graph.events` | the audit trail, and what the projector and SSE stream read |
| `graph.approvals` | an agent needs a person; resumes a checkpointed graph |
| `graph.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `cache:path:{start}:{hops}` | traversals repeat across questions |
| `lock:ingest:{doc}` | one builder per document |
| `idem:doc:{sha256}` | corpora ship duplicates |
| `live:graph` | node and edge counters |

**Postgres:** Postgres for documents and answers; **Neo4j** for the graph itself. `documents, mentions, queries, answers, contradictions, events`.

**UI:** React + Cytoscape.js — the graph is the interface, not a decoration beside it.

## Real data

`Morson/mimic_ex` — 220 MB, **not** gated, the workable substitute for MIMIC-IV. ⚠️ The paper's middle tier (MedC-K / S2ORC) is a dead end: the authors cannot release raw content. Say that in the README. UMLS is free but needs an application — submit it early. ⚠️ The 'ACL 2025' claim on the source repo returned nothing from Semantic Scholar; verify before citing.

## The deterministic core

`src/graphclinic/domain.py` decides a bounded, cycle-safe walk that carries the source of every edge it crossed. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not diagnose or advise on treatment.** It retrieves and cites.
- **It does not infer an edge.** An edge exists because a document stated it, and the edge names the document.
- **It does not walk unbounded.** Hop limits are arguments, not conventions.
- **It does not reproduce the paper.** Two of three data tiers are reachable; the middle one is not, and the README says so.

## Problems hit while building this

- The first traversal followed cycles forever on a graph where two conditions each 'relate to' the other. Visited-set plus a hop cap, both tested.
- Provenance had to live on the edge, not on the node. An answer that names its entities but not the documents that connected them is not checkable.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
