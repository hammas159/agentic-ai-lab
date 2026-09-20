# 01 · revenue-desk

> Multi-agent CRM and lead engine whose forecast is arithmetic and whose agents cannot overwrite you.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 17 lead-scout, and 25 web-operator as a tool.

## The finding it exists to produce

How often an agent's update reverts a human's earlier correction on the same field.
Last-writer-wins is the default in every CRM integration and it is silently destructive.
Report the revert rate before and after field-level provenance, on the same traffic.

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

## What it does NOT do

- **It does not send.** The writer agent produces drafts; sending is a human action behind an approval.
- **It does not scrape a platform that forbids it.** Sources are search, public registers and sites that permit crawling.
- **It does not score a lead with a model.** Fit is a rules-and-weights calculation the buyer can read.
- **It does not resolve a provenance conflict.** It surfaces one and stops.

## Problems hit while building this

- The first forecast summed `amount` and asked the model to 'weight by stage'. Two runs on identical data gave figures 11% apart, which is how this rule got written.
- Revert detection needs the *order* of edits, not their timestamps — two edits inside one second are common and clock skew between workers is real. The core takes a sequence number.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
