# 05 · comms-desk

> Email and meetings reconciled into one board of commitments, each attributed to who made it.

**Status:** runs end to end. Intake is accepted onto the bus and returns; a worker drains
it; the graph pauses for a person; approving resumes it without regenerating anything. It
serves the shared operator console at `/`.

**Absorbs:** `BUILD-PLAN.md` 03 inbox-pilot and 04 meeting-scribe. The merge is the point: a thread and a meeting are two sources of one object.

## The finding

**Measured on the AMI Meeting Corpus** — 12 real recorded meetings, 9,550 hand-annotated
dialogue acts across 48 speaker slots, of which **922 are Suggest or Offer**: the acts that
put someone on the hook.

| Similarity threshold | Duplicates found | Speaker-blind | **Wrong merges** |
|---:|---:|---:|---:|
| 0.5 | 10 | 26 | **16 — 62% of everything it merged** |
| 0.6 | 6 | 9 | 3 |
| 0.7 | 3 | 3 | 0 |

**At the threshold you need to catch genuine restatements, ignoring who spoke makes 26
merges of which 16 join two different people's commitments.** Sixty-two per cent of the
merging is wrong, and each wrong merge deletes someone's promise from the board.

Tightening the threshold does make the damage vanish — along with the benefit. At 0.7,
nothing merges across speakers and almost nothing merges at all. There is no threshold that
separates the two, which is why **speaker is a hard barrier here and never a weighted
feature in a similarity score.** There is a test asserting no threshold, however loose,
merges across speakers.

### What this corpus cannot show, said plainly

The within-meeting duplicate rate is about **1%** — people rarely restate a commitment
inside one conversation. The duplication this product is built for is **cross-source**: the
same promise made in a meeting and repeated in a follow-up email. AMI is meetings only, so
that rate is not measurable here and is not claimed. What AMI does establish is the thing
that matters more: the merge step is where this class of product breaks, and the speaker
barrier is what stops it.

Reproduce it:

```bash
cd 05_comms-desk && python -m pytest tests/test_real_meetings.py -q     # 8 passed
```

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `triage` | `threads.category`, including an explicit abstain class | archiving or deleting |
| `transcriber` | `transcripts` (ASR plus diarisation) | an unattributed line |
| `extractor` | `commitments` with speaker and timestamp | a commitment with no source span |
| `reconciler` | links between commitments and threads | merging two low-confidence items |
| `reply-writer` | `drafts` | sending — no exception |
| `scheduler` | `proposed_slots` from free/busy | booking without approval |

## Architecture

| Topic | Carries |
|---|---|
| `comms.intake` | everything arriving from outside |
| `comms.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `comms.events` | the audit trail, and what the projector and SSE stream read |
| `comms.approvals` | an agent needs a person; resumes a checkpointed graph |
| `comms.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:{mailbox}:{rfc822_id}` | IMAP redelivers on reconnect |
| `lock:thread:{id}` | one triage run per thread |
| `ctx:{thread}` | working memory across a thread's turns |
| `cache:freebusy:{calendar}` | CalDAV is slow and repeats |

**Postgres:** `threads, messages, meetings, transcripts, commitments, drafts, slots, events`.

**UI:** Svelte 5 (runes) — triage queue, transcript with speaker lanes, and a single commitments board fed by both sources.

## Real data

The **Enron corpus** (~500k real emails) for triage, and the **AMI Meeting Corpus** — real recordings with reference transcripts and annotations — for extraction. Both openly available.

## The deterministic core

`src/comms/domain.py` decides which commitments are the same commitment, and which merges must never happen. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## Running it

```bash
cd 05_comms-desk
python -m pytest -q                      # 14 passed
PYTHONPATH="src;../platform/src" python -m comms.app    # console on http://127.0.0.1:8000
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

- **It does not send.** Not once, not with a confirmation dialogue.
- **It does not archive or delete mail.** Categories only.
- **It does not keep a commitment it cannot attribute.** No speaker and timestamp, no row.
- **It does not merge across speakers.** Two people promising similar things are two commitments.

## Problems hit while building this

- The first merger used text similarity alone and combined a promise by one attendee with a similar promise by another. Speaker identity is now a hard barrier, not a feature in a score.
- Similarity needed a floor on length. Two three-word commitments match each other trivially and almost never mean the same thing.

## Input / Output

Captured from a real run of this product — `scripts/capture.py` submits the payload below
through the HTTP surface, drains the queue, and approves. Every figure here came off a
machine.

**In** — `POST /intake`, keys: `claims`, `commitments`, `issued_receipts`

Published to `comms.tasks`; the call returns `202 {"status": "pending"}` with queue lag
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
| Result keys | `branch_status`, `branches`, `branches_failed`, `claims`, `clusters`, `commitments`, `draft`, `drop_rate`, `dropped_claims`, `duplicates`, `issued_receipts`, `kept_claims`, `model`, `sent`, `summary`, `summary_subject` |

**The early exit**, on a payload that trips `nothing_to_do`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `triage` → `exit` |
| Model calls | **0** |

That last row is the one worth keeping. The cheap refusal costs nothing at all — no
gather, no generation — which is the whole reason it sits before the fan-out.
