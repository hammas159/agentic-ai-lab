# 05 · comms-desk

> Email and meetings reconciled into one board of commitments, each attributed to who made it.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 03 inbox-pilot and 04 meeting-scribe. The merge is the point: a thread and a meeting are two sources of one object.

## The finding it exists to produce

The same commitment arrives twice — once in a meeting, once in a follow-up email — in
different words. Measure the duplicate rate. Every tool in this space silently doubles the
user's task list, and the merge step is exactly where an LLM matcher over-merges two
different promises made by two different people.

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

## What it does NOT do

- **It does not send.** Not once, not with a confirmation dialogue.
- **It does not archive or delete mail.** Categories only.
- **It does not keep a commitment it cannot attribute.** No speaker and timestamp, no row.
- **It does not merge across speakers.** Two people promising similar things are two commitments.

## Problems hit while building this

- The first merger used text similarity alone and combined a promise by one attendee with a similar promise by another. Speaker identity is now a hard barrier, not a feature in a score.
- Similarity needed a floor on length. Two three-word commitments match each other trivially and almost never mean the same thing.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
