# 03 · one-desk

> Portfolio, LinkedIn, Instagram and X in one calendar, one inbox and one approval tray.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Per-platform 'voice adaptation' is the selling point of every tool in this category.
Measure token overlap between the variants. The likely result is that three of four are
near-identical past length and hashtags, and that the engagement difference is explained by
posting time — which is deterministic and needs no model. Publish it either way.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `planner` | `calendar` slots | published content |
| `adapter` | `post_variants` | `posts.published` |
| `brand-guard` | a veto, with a reason | anything else |
| `comment-triage` | `threads.intent`, the escalation flag | a public reply |
| `reply-writer` | `reply_drafts` | auto-publishing, ever |
| `analyst` | `metrics_rollups` (computed) | a metric it did not fetch |

## Architecture

| Topic | Carries |
|---|---|
| `social.intake` | everything arriving from outside |
| `social.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `social.events` | the audit trail, and what the projector and SSE stream read |
| `social.approvals` | an agent needs a person; resumes a checkpointed graph |
| `social.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:slot:{platform}:{time}` | prevents the same slot publishing twice |
| `ratelimit:{platform}` | four APIs, four different limits |
| `idem:{platform}:{webhook_id}` | webhook deliveries repeat |
| `live:engagement` | dashboard counters without a query |

**Postgres:** `ideas, calendar, post_variants, posts, threads, reply_drafts, metrics, events`.

**UI:** Preact + Signals — four-column calendar, unified inbox, approval tray, one analytics page comparing platforms on the same axis.

## Real data

Your own accounts and your own post history. The one product here whose demo data is genuinely yours and genuinely real.

## The deterministic core

`src/onedesk/domain.py` decides how much two platform variants actually differ, and when your own history says to post. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not auto-reply in public.** Drafts only, always.
- **It does not buy engagement, follow, or mass-DM.** Nothing here touches a growth-hacking pattern.
- **It does not claim a metric it did not fetch.** Every figure carries its fetch time.
- **It does not use a model to pick a posting time.** That is a count over your own history.

## Problems hit while building this

- Overlap was first measured with a plain token set, which called two posts identical because they shared stop words. Containment against the baseline variant, over content words, is the version that says anything.
- Hashtags inflated apparent difference while changing nothing about the text, so they are stripped before comparison and reported separately.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
