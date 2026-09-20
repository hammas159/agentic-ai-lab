# 06 · oncall-mate

> An alert storm collapsed into one incident with a suspect, a runbook and a status update.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 11, plus the four queued `incident-copilot` upgrades. Built on the `incident-copilot` core; distinct from it because that is a library and a CLI and this is the product.

## The finding it exists to produce

`log-detective` found that compression destroys the rare line — 655 of ~1,000 distinct
messages gone, templates-seen-once falling from 908 to 150. The rare line is what an
incident is made of. Measure suspect accuracy as a function of template compression ratio,
and find where the two curves cross.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `correlator` | `incidents`, `alert_links` — deterministic | a hypothesis |
| `hypothesiser` | `hypotheses`, each with linked evidence ids | an unevidenced hypothesis |
| `change-attributor` | `suspect_changes`, ranked by diff statistics | a suspect with no deploy record |
| `runbook-selector` | `proposed_actions` | executing anything |
| `comms-writer` | `status_drafts` | publishing |
| `pir-writer` | `reviews.draft` | a cause absent from the timeline |

## Architecture

| Topic | Carries |
|---|---|
| `ops.intake` | everything arriving from outside |
| `ops.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `ops.events` | the audit trail, and what the projector and SSE stream read |
| `ops.approvals` | an agent needs a person; resumes a checkpointed graph |
| `ops.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `dedupe:{fingerprint}` | the same alert fires every 30s until resolved |
| `lock:incident:{id}` | one correlator per incident |
| `live:board` | the wall display reads counters, not queries |
| `cache:promql:{sha}` | the same range query repeats across hypotheses |

**Postgres:** `alerts, incidents, hypotheses, evidence, changes, actions, reviews, events`.

**UI:** A dense realtime board, built to live on a wall screen and survive a browser restart.

## Real data

**Loghub** — HDFS, BGL and Thunderbird, real public log datasets with labelled anomalies. `log-detective` already ran on 1,005 real lines captured on this machine; this is the scale-up, and it resolves the 'needs real alerts' blocker that held this project up.

## The deterministic core

`src/oncall/domain.py` decides which alerts belong to one incident, and refuses to chain unrelated services into a single storm. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not execute a remediation.** It proposes; a person runs it.
- **It does not show a hypothesis without its evidence.** No evidence link, no row.
- **It does not page on its own** unless a rule a human wrote says to.
- **It does not rank blast radius by opinion.** Diff statistics, reusing `release-captain`'s work.

## Problems hit while building this

- `incident-copilot` already found this the hard way: correlation inside a time window is transitive, so an evenly-spaced drip collapses unrelated services into one critical incident. The core caps total span and defaults to requiring service affinity.
- Deduplication by message text was wrong — the same fault produces a message with a different host in it each time. Fingerprints come from the template, not the line.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
