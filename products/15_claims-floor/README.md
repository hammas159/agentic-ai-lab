# 15 · claims-floor

> Insurance claims from first notice to settlement pack, against the policy wording that was actually in force.

**Status:** runs end to end. Intake is accepted onto the bus and returns; a worker drains
it; the graph pauses for a person; approving resumes it without regenerating anything. It
serves the shared operator console at `/`.

## The finding

**Measured on real versioned regulation** — the eCFR version index for Title 29 (Labor):
1,000 real section versions across 577 sections, each with the date its amendment took
effect.

| | |
|---|---:|
| Sections | 577 |
| **Amended more than once** | **272 (47%)** |
| Median versions per amended section | 2 (max 11) |
| Questions where the date matters | 695 |
| **Answered wrongly by returning the current text** | **363 (52.2%)** |
| Worst case, how far out the returned text was | **9.6 years** |

**For a section that has ever been amended, answering from the current text answers a
different question half the time.** The answer is fluent, it cites a real section, and it is
about a different set of words than the one that governed the event.

The median gap is under a year, because most amendments are recent. **The tail is what
decides a claim wrongly** — nearly a decade of intervening amendments, invisible in the
output.

So the product refuses rather than defaults. A loss date with no wording in force raises
`NoVersionInForceError`; overlapping versions raise too. Falling back to the latest was the
first behaviour written here and is exactly the bug.

### Why regulation rather than policy wordings

Insurers do not publish a machine-readable archive of superseded wordings. A section of
regulation with a version history and an effective date is structurally the same object as a
policy wording with a version history and a loss date — and it is real. Inventing an archive
would have produced a number that measured the invention.

### Something the data taught

Several sections carry two entries with the **same** amendment date. A test case chosen
without checking for that failed spuriously, and the duplicate-date case is now asserted
rather than worked around, because a version history is not guaranteed to be a clean
sequence of distinct dates.

Reproduce it:

```bash
cd 15_claims-floor && python -m pytest tests/test_real_versions.py -q     # 10 passed
```

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

## Running it

```bash
cd 15_claims-floor
python -m pytest -q                      # 17 passed
PYTHONPATH="src;../platform/src" python -m claimsfloor.app    # console on http://127.0.0.1:8000
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

- **It does not decline a claim.** It reports coverage and the clause; a person declines.
- **It does not pay.** Settlement packs are drafts.
- **It does not score fraud with a model.** Rules that name themselves when they fire.
- **It does not read an unpinned wording.** A claim with no version in force is an error, not a default to the latest.

## Problems hit while building this

- Defaulting to the current wording when no version covered the loss date was the first behaviour and is exactly the bug. It raises now.
- Overlapping version ranges are common in real policy books after an endorsement, and silently picking the first match hides them. Overlaps raise too.

## Input / Output

Captured from a real run of this product — `scripts/capture.py` submits the payload below
through the HTTP surface, drains the queue, and approves. Every figure here came off a
machine.

**In** — `POST /intake`, keys: `claims`, `issued_receipts`, `loss_date`, `peril`, `versions`

Published to `claims.tasks`; the call returns `202 {"status": "pending"}` with queue lag
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
| Result keys | `branch_status`, `branches`, `branches_failed`, `claims`, `coverage_reason`, `covered`, `draft`, `drop_rate`, `dropped_claims`, `issued_receipts`, `kept_claims`, `loss_date`, `model`, `no_version`, `paid`, `peril`, `settlement.draft`, `summary`, `summary_subject`, `version_id`, `versions` |

**The early exit**, on a payload that trips `cannot_assess`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `triage` → `exit` |
| Model calls | **0** |

That last row is the one worth keeping. The cheap refusal costs nothing at all — no
gather, no generation — which is the whole reason it sits before the fan-out.
