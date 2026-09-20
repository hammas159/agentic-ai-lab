# 15 · claims-floor

> Insurance claims from first notice to settlement pack, against the policy wording that was actually in force.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Coverage decisions turn on the exclusions clause, and the real failure is the wrong policy
*version*, not the reading. Measure how often retrieval returns a superseded wording for a
claim whose loss date falls under an earlier one. That error is invisible in the output —
the answer is fluent, cites a real clause, and is wrong.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `fnol-intake` | `claims`, `loss.date`, `loss.description` | a coverage decision |
| `coverage-checker` | `coverage` — from the version-pinned wording | reading a version that was not in force |
| `fraud-scorer` | `claims.signals` with the rule that fired | declining a claim |
| `adjuster-router` | `assignments` — solver output | reassigning to clear a queue |
| `settlement-writer` | `settlements.draft` | paying |
| `qa-sampler` | `qa_reviews` | overriding an adjuster |

## Architecture

| Topic | Carries |
|---|---|
| `claims.intake` | everything arriving from outside |
| `claims.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `claims.events` | the audit trail, and what the projector and SSE stream read |
| `claims.approvals` | an agent needs a person; resumes a checkpointed graph |
| `claims.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:claim:{id}` | two agents on one claim is how a duplicate payment happens |
| `cache:wording:{policy}:{version}` | the same wording is read by every agent on the claim |
| `idem:fnol:{reference}` | a claim reported by phone and by form is one claim |
| `live:sla` | ageing against the regulator's clock |

**Postgres:** `policies, policy_versions, claims, coverage, signals, assignments, settlements, events`.

**UI:** Nuxt 4 — a claim queue, a coverage view showing the clause and its version, a settlement composer.

## Real data

Synthetic claims against **real published policy wordings**, which insurers publish openly, with genuine version-effective dates. The wording versions are the part that has to be real; the claims do not.

## The deterministic core

`src/claimsfloor/domain.py` decides which policy version was in force on the loss date, and refuses to answer from any other. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not decline a claim.** It reports coverage and the clause; a person declines.
- **It does not pay.** Settlement packs are drafts.
- **It does not score fraud with a model.** Rules that name themselves when they fire.
- **It does not read an unpinned wording.** A claim with no version in force is an error, not a default to the latest.

## Problems hit while building this

- Defaulting to the current wording when no version covered the loss date was the first behaviour and is exactly the bug. It raises now.
- Overlapping version ranges are common in real policy books after an endorsement, and silently picking the first match hides them. Overlaps raise too.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
