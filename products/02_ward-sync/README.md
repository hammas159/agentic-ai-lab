# 02 · ward-sync

> Hospital operations agents: intake, bed and theatre assignment, result routing, discharge, pre-authorisation.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** the queued `clinical-triage-crew`, and `BUILD-PLAN.md` 02 voice-desk as the phone intake channel.

## The finding it exists to produce

A discharge-summary agent reads the *current* medication list and writes a drug that was
discontinued on day two. Current state and event history disagree, and the model is handed
the wrong one. Measure the rate; regenerate from the event stream and measure it again.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `intake` | `encounters`, `patient.demographics` | any clinical field |
| `triage-router` | `encounter.department`, `encounter.acuity_band` | a diagnosis |
| `bed-planner` | `assignments` — solver output only | an assignment that breaks a constraint |
| `results-router` | `notifications` | a result value |
| `discharge-writer` | `summaries.draft` | `summaries.final` — a clinician signs |
| `preauth-packer` | `claims.draft`, the attachment list | a justification not in the record |

## Architecture

| Topic | Carries |
|---|---|
| `ward.intake` | everything arriving from outside |
| `ward.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `ward.events` | the audit trail, and what the projector and SSE stream read |
| `ward.approvals` | an agent needs a person; resumes a checkpointed graph |
| `ward.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:bed:{id}` | double-booking a bed is the classic failure here |
| `live:occupancy` | the floor board reads this, not Postgres |
| `ctx:{encounter}` | working memory for one encounter's run |
| `idem:lab:{result_id}` | lab interfaces redeliver on reconnect |

**Postgres:** `patients, encounters, assignments, orders, results, summaries, claims, events` — `events` is the clinical audit log and the source of truth for state.

**UI:** Refine + Ant Design — floor board, encounter timeline, clinician sign-off queue, pre-auth tray.

## Real data

**Synthea** — open source, generates complete synthetic patient histories in FHIR with no credentialing. Optionally MIMIC-IV-demo, 100 patients, openly available.

## The deterministic core

`src/ward/domain.py` decides which medications are actually active, and which drafted sentences have no event to stand on. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not diagnose.** Not a clinical decision tool; an operations tool. That is both the ethical position and the commercially real one.
- **It does not sign anything.** Every clinical artefact stops at draft.
- **It does not assign a bed with a model.** Assignment is a constraint solver; the model explains the result.
- **It does not read a medication list.** It reads the event stream, which is the entire point.

## Problems hit while building this

- The first version took the current medication list because it was one query. It produced a summary naming a drug stopped on day two — the finding this product now exists to measure.
- 'Active' needed defining. A drug ordered, discontinued, then ordered again is active; a naive set difference says it is not.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
