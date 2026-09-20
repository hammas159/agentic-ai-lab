# 07 · hire-desk

> CV parsing, blind scoring against a fixed rubric, an interview kit, and a fairness audit that runs continuously.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 18.

## The finding it exists to produce

Run every CV twice, identified and redacted, and measure the score delta. 'Blind scoring
works' is testable in one afternoon on this hardware and nobody publishes the number.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `cv-parser` | `candidates.fields` with confidence | a score |
| `redactor` | `redacted_views` — deterministic | anything else |
| `scorer` | `scores` per rubric dimension, from the redacted view only | a free-text overall verdict |
| `kit-builder` | `interview_kits` | a question outside the rubric |
| `scheduler` | `slots` | booking without approval |
| `fairness-auditor` | `audit_reports` | suppressing a measure |

## Architecture

| Topic | Carries |
|---|---|
| `hire.intake` | everything arriving from outside |
| `hire.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `hire.events` | the audit trail, and what the projector and SSE stream read |
| `hire.approvals` | an agent needs a person; resumes a checkpointed graph |
| `hire.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:cv:{sha256}` | the same CV arrives via three job boards |
| `lock:candidate:{id}` | one scoring run per candidate |
| `budget:{role}:{day}` | bulk intake must not eat a day's tokens |
| `cache:parse:{sha256}` | re-parsing a CV is pure waste |

**Postgres:** `roles, candidates, redacted_views, scores, kits, interviews, audits, events`.

**UI:** Ember Octane, or FastAPI + Jinja + Tailwind if Ember is not worth the learning cost — a role board, a blind-scoring queue, and a standing fairness page.

## Real data

`D:\\github\\_research\\extracted.jsonl` for the roles, a public résumé corpus for the candidates, and **name-swapped duplicates** for the fairness audit — the same CV under several names is the only honest way to measure this. ⚠️ This product does not start until a real CV corpus is sourced; inventing CVs breaks the no-fabricated-dataset rule.

## The deterministic core

`src/hiredesk/domain.py` decides what the scorer is allowed to see, and whether anything identifying survived redaction. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not reject a candidate.** It scores against a published rubric and ranks.
- **It does not let the scorer see an identified record.** The scoring worker consumes a different topic; it is structurally unable to.
- **It does not produce an overall verdict from a model.** Dimensions are structured-decoded and summed in Python.
- **It does not report one fairness measure.** All four incompatible ones, the `credit-risk-engine` pattern.

## Problems hit while building this

- Dropping identifying *keys* was not enough. The name reappeared in the free-text summary field, and the education section named a school that identifies a city. Redaction has to scrub the free text, and a leak check has to prove it did.
- The redaction barrier reads better as a topic boundary than as a function call — a reviewer can see the scorer cannot receive the identified record, rather than trusting that it does not read it.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
