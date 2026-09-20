# 09 · hermes-home

> Self-hosted personal agent: durable memory that is gated on contradiction, an MCP tool surface, self-authored skills.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 01. The flagship, and the repo where `../platform` actually lives.

## The finding it exists to produce

What fraction of proposed memories contradict an existing one, and what happens to
long-horizon accuracy when you accept them all versus gate them. `langchain-lab 03` already
showed hard constraints are what gets lost, so the measurement is **hard-constraint survival
at 50 turns, gated versus ungated**. That single chart is the strongest thing in the
portfolio.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `conversation` | `messages`, `ctx:` | semantic memory |
| `memory-proposer` | `memory_candidates` | `memories` |
| `contradiction-checker` | `memories` — the only writer | a hard constraint, which a person settles |
| `skill-author` | `skills.draft` | `skills.active` |
| `tool-broker` | `tool_calls` | a call outside the allow-list |

## Architecture

| Topic | Carries |
|---|---|
| `home.intake` | everything arriving from outside |
| `home.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `home.events` | the audit trail, and what the projector and SSE stream read |
| `home.approvals` | an agent needs a person; resumes a checkpointed graph |
| `home.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `ctx:{conversation}` | working memory on the reply path |
| `lock:conversation:{id}` | two surfaces, one conversation |
| `llmcache:{sha}` | the same question from two surfaces |
| `ratelimit:{surface}` | web, Telegram and CLI have different budgets |

**Postgres:** `conversations, messages, memory_candidates, memories (with supersedes / contradicted_by edges), skills, tool_calls, events` — plus pgvector.

**UI:** Tauri desktop, plus a Telegram surface.

## Real data

Your own use, measured against **LongMemEval** and **LoCoMo** — public long-term-memory benchmarks with ground truth, so the memory claim is a number rather than a feeling.

## The deterministic core

`src/hermes/domain.py` decides which constraints must travel with a handoff, and refuses the handoff when a hard one would be dropped. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not write semantic memory from the reply path.** Memory writes run off `home.events`, so they never add latency to an answer.
- **It does not activate a skill it wrote.** Drafts only.
- **It does not call a tool outside the allow-list**, whatever the conversation says.
- **It does not resolve a hard-constraint contradiction.** It asks.

## Problems hit while building this

- `langgraph-lab 05` found that passing only the latest message to a handed-off specialist dropped safety from 100% to 20% — recommending eggs to a vegan, a hotel with no accessibility note to someone who required one. The core makes that a refusal rather than a prompt instruction.
- The naive summariser in `langchain-lab 03` kept 100% of soft preferences and 0% of hard constraints. Hard and soft are therefore separate types here, not a confidence score.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
