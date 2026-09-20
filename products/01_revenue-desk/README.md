# 01 · revenue-desk

> Multi-agent CRM and lead engine whose forecast is arithmetic and whose agents cannot overwrite you.

**Status:** runs end to end. Intake is accepted onto the bus and returns; a worker drains
it; the graph pauses for a person; approving resumes it without regenerating anything. It
serves the shared operator console at `/`.

**Absorbs:** `BUILD-PLAN.md` 17 lead-scout, and 25 web-operator as a tool.

## The finding

This product exists to measure how often one writer's update destroys another's recent
correction. There is no CRM log on this machine to measure that on — so rather than invent
one, the same *mechanism* is measured on the largest real corpus of dated edits available:
**the git history of the repositories on this disk.**

A revert is a line that went A, then B, then back to A. Not a rewrite, not churn — one edit
undoing another, which is exactly what `detect_reverts` looks for on a deal record.

| | |
|---|---:|
| Repositories surveyed | 12 |
| Line edits examined | **232,160** |
| True reverts (A to B to A) | 234 |
| **Revert rate** | **0.10%** |
| Median gap between removal and restoration | 1 commit (max 23) |

**One edit undoes another about once in a thousand — in a medium with diffs, atomic commits
and review.** That is the floor such controls achieve, and it is the useful number: a CRM
field has none of them. No diff is shown, no commit is atomic, nothing is reviewed, and the
writer is often a process rather than a person.

The spread between repositories is more than twenty-fold. Exploratory work rewrites itself;
finished work does not.

### What is not claimed

**The agent-versus-human revert rate in a CRM is not measured here**, because no such log
exists on this machine. What is established is the floor, the detector, and the fact that
the detector finds real reverts in real history rather than only in fixtures. The product's
provenance mechanism — field-level ownership, an agent allowed to propose but not overwrite
a human-owned field — is built because you cannot reach that floor without controls, not
because a number here proves a CRM is worse.

Saying so is the point. A README claiming a measured CRM revert rate would be claiming a
measurement that was never made.

### One thing the test caught

`find_reverts` originally relied on the git parser to skip trivial lines, so a caller
building edits directly could get a closing brace reported as a revert. Whether a line is
substantial enough to count is a property of revert detection, not of where the edits came
from, and it now lives there.

Reproduce it:

```bash
cd 01_revenue-desk && python -m pytest tests/test_real_reverts.py -q     # 8 passed
```

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `scout` | `leads` (new rows) | an existing lead's fields |
| `enricher` | `company.*` facts, each with a source URL | anything on a deal |
| `qualifier` | `lead.score`, `lead.stage` (rules-derived) | a stage jump greater than one |
| `writer` | `drafts` | `messages` — it never sends |
| `reply-classifier` | `reply.intent`, `contact.opted_out` | clearing an opt-out |
| `deal-analyst` | `deal.risk_factors` | `deal.amount`, `deal.close_date` — proposes only |
| `forecaster` | nothing; it reads | every field |

## Architecture

| Topic | Carries |
|---|---|
| `crm.intake` | everything arriving from outside |
| `crm.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `crm.events` | the audit trail, and what the projector and SSE stream read |
| `crm.approvals` | an agent needs a person; resumes a checkpointed graph |
| `crm.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:gmail:{message_id}` | mail providers redeliver, constantly |
| `lock:deal:{id}` | two agents must never write one deal at once |
| `budget:{mailbox}:{day}` | a token ceiling that is also a deliverability control |
| `llmcache:{sha}` | enrichment prompts repeat across a sequence |

**Postgres:** `accounts, contacts, deals, activities, drafts, suppression, agent_runs, approvals, events` — with a provenance column on every agent-writable field.

**UI:** Angular 19 — pipeline board, per-deal timeline showing which agent wrote which field, approvals queue, forecast page.

## Real data

`D:\\github\\_research\\extracted.jsonl` — 247 records already mined from 286 hiring-post screenshots. Companies hiring AI engineers *are* the lead list. Plus the SECP public register and OpenCorporates.

## The deterministic core

`src/revenue/domain.py` decides the forecast figure and which agent edits are reverts. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## Running it

```bash
cd 01_revenue-desk
python -m pytest -q                      # 21 passed
PYTHONPATH="src;../platform/src" python -m revenue.app    # console on http://127.0.0.1:8000
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

- **It does not send.** The writer agent produces drafts; sending is a human action behind an approval.
- **It does not scrape a platform that forbids it.** Sources are search, public registers and sites that permit crawling.
- **It does not score a lead with a model.** Fit is a rules-and-weights calculation the buyer can read.
- **It does not resolve a provenance conflict.** It surfaces one and stops.

## Problems hit while building this

- The first forecast summed `amount` and asked the model to 'weight by stage'. Two runs on identical data gave figures 11% apart, which is how this rule got written.
- Revert detection needs the *order* of edits, not their timestamps — two edits inside one second are common and clock skew between workers is real. The core takes a sequence number.

## Input / Output

Captured from a real run of this product — `scripts/capture.py` submits the payload below
through the HTTP surface, drains the queue, and approves. Every figure here came off a
machine.

**In** — `POST /intake`, keys: `claims`, `issued_receipts`, `reply`, `signals`

Published to `crm.tasks`; the call returns `202 {"status": "pending"}` with queue lag
**1**. Nothing has touched the model at this point.

**Out** — after one worker pass:

| | |
|---|---|
| Status | `awaiting_approval`, paused at `approve` |
| Nodes visited | `classify` → `qualify` → `enrich` → `synthesise` → `draft` → `gate` → `approve` |
| Model calls already spent | **2** |
| Claims kept by the gate | "They are hiring three AI engineers." |
| Claims dropped | "They are evaluating vendors this quarter." |
| Drop rate | 0.5 |

After `POST /approvals/{run}/approve`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `classify` → `qualify` → `enrich` → `synthesise` → `draft` → `gate` → `approve` → `send` |
| Model calls | **2** — resuming added none |
| Result keys | `branch_status`, `branches`, `branches_failed`, `claims`, `draft.body`, `drop_rate`, `dropped_claims`, `issued_receipts`, `iterations`, `kept_claims`, `lead.score`, `lead.stage`, `model`, `reply`, `reply.intent`, `sent`, `signals`, `summary` |

**The early exit**, on a payload that trips `suppressed`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `classify` → `suppress` |
| Model calls | **0** |

That last row is the one worth keeping. The cheap refusal costs nothing at all — no
gather, no generation — which is the whole reason it sits before the fan-out.
