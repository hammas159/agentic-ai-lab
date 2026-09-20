# 18 · campus-ops

> Education administration: admissions, timetabling, fee reconciliation, attendance and parent communications.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Timetable clash detection is a solver property and every clash it finds is one a person
would have found in week three of term. Measure clashes per published timetable at a real
institution before the solver and after, and separately measure how many the *model* found
when asked — the gap is the argument for keeping scheduling out of a prompt.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `applicant-parser` | `applications.fields` with confidence | an admission decision |
| `eligibility-checker` | `eligibility` from published rules | an offer |
| `scheduler` | `timetables` — solver output only | publishing over a clash |
| `fee-reconciler` | `payments`, `matches` | waiving a fee |
| `parent-comms` | `messages.draft` | sending |
| `policy-answerer` | `answers` with the regulation cited, plus an abstain class | an answer from an unversioned policy |

## Architecture

| Topic | Carries |
|---|---|
| `campus.intake` | everything arriving from outside |
| `campus.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `campus.events` | the audit trail, and what the projector and SSE stream read |
| `campus.approvals` | an agent needs a person; resumes a checkpointed graph |
| `campus.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:timetable:{term}` | two schedulers publishing one term is a term of chaos |
| `cache:rules:{version}` | eligibility rules are read by every application |
| `idem:payment:{reference}` | bank files are re-imported |
| `live:attendance` | today's counters |

**Postgres:** `applicants, applications, cohorts, teachers, rooms, sessions, timetables, fees, payments, events`.

**UI:** HTMX + Jinja2 — an administrator's tool, server-rendered, works on the office machine that exists.

## Real data

Published university prospectuses and fee schedules, which are real and open, plus a generated cohort of the right size. The constraints have to be real; the students do not.

## The deterministic core

`src/campusops/domain.py` decides whether a timetable clashes with itself, in the three ways it can. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not admit or reject anyone.** Eligibility against published rules; a person decides.
- **It does not publish a timetable with a clash.** NotAuthorisedError, not warned about.
- **It does not waive or refund a fee.**
- **It does not answer a policy question from an unversioned document.** It abstains, and abstention rate is a reported metric.

## Problems hit while building this

- Three clash types, not one: a room double-booked, a teacher double-booked, a cohort double-booked. The first version checked rooms only and published a timetable where a lecturer taught two classes at once.
- Back-to-back sessions were flagged as clashes until the boundary was made half-open. A session ending at 10:00 and one starting at 10:00 do not overlap.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
