# 19 · agri-desk

> Crop advisory over your own surveillance data, offline first, with an explicit escalation path.

**Status:** runs end to end. Intake is accepted onto the bus and returns; a worker drains
it; the graph pauses for a person; approving resumes it without regenerating anything. It
serves the shared operator console at `/`.

## The finding

**Measured, on 60 real Cotton leaf curl virus genomes from NCBI GenBank.**

| | |
|---|---|
| Records in the corpus | 60 |
| Distinct sequences, counted naively | **60** |
| Distinct observations after collapsing clonal duplicates | **41** |
| Records that were a sequence already seen at that site | 19 (32%) |
| Largest clonal group | **8 identical genomes** — `ON312781`–`ON312788`, one submission |
| Variants that look like they are emerging | **10** |
| Variants still emerging once a variant must appear at more than one site | **0** |
| False-alarm rate | **1.000** |

Every one of the ten emergence calls is spurious. The signal was the same isolate sequenced
repeatedly and submitted as a batch: `CLCMV/S2-1` through `CLCMV/S2-8` are eight genomes
from one field, one submission and one haplotype, and a neighbouring batch
(`CLCMV/NIA-*`, 5 records) is identical to itself as well.

An advisory agent reading the uncollapsed feed warns a farmer about an outbreak that is not
happening. That is not a hypothetical: `clcuv-surveillance` recorded exactly this failure
producing nine "significantly emerging" variants at z > 3, every number computed correctly
and the conclusion worthless, because the test was told there were sixteen independent
observations when there were two.

**The unit of replication is not the row.** It is the same bug as a research agent counting
one wire story republished by twelve outlets as twelve corroborating sources.

Reproduce it:

```bash
cd 19_agri-desk && python -m pytest tests/test_real_corpus.py -q     # 11 passed
```

### One thing that had to be fixed to get this number

GenBank renamed `/country` to `/geo_loc_name`. The first version of the reader looked for
the old name, found nothing, and defaulted every record's site to `"unknown"` — which
merges Pakistan, India and China into one stratum. That over-collapses clonal duplicates
*and* hides the multi-site spread emergence is defined by, in opposite directions at once,
while looking like it works. There is a test pinning the three real sites.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `report-parser` | `field_reports.fields` | an advisory |
| `surveillance-linker` | `links` to collapsed variant clusters | a variant call |
| `agronomy-retriever` | `evidence` with a dated source | an undated recommendation |
| `advisory-writer` | `advisories.draft` | an advisory with no evidence attached |
| `price-reporter` | `prices` — fetched, with the market and date | a price it did not fetch |
| `escalation-router` | `escalations` | answering outside the evidence base |

## Architecture

| Topic | Carries |
|---|---|
| `agri.intake` | everything arriving from outside |
| `agri.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `agri.events` | the audit trail, and what the projector and SSE stream read |
| `agri.approvals` | an agent needs a person; resumes a checkpointed graph |
| `agri.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `queue:offline:{device}` | reports queue on the handset until it reconnects |
| `idem:report:{device}:{local_id}` | a queued report is re-sent on every reconnect |
| `cache:weather:{cell}:{day}` | one fetch per grid cell per day |
| `lock:cluster:{id}` | one linker per variant cluster |

**Postgres:** `field_reports, images, isolates, clusters, advisories, evidence, prices, escalations, events`.

**UI:** Lit 3 as a PWA, offline first — a field has no signal, and an advisory tool that needs one is not a tool.

## Real data

**Real NCBI GenBank sequences** already committed in `clcuv-surveillance` (`data/clcuv.gb`, 532 KB), plus published agronomy guidance and open market-price feeds. The surveillance half of this product is already built and measured.

## The deterministic core

`src/agridesk/domain.py` decides how many distinct variants there really are, once the same isolate sequenced repeatedly stops counting as several. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## Running it

```bash
cd 19_agri-desk
python -m pytest -q                      # 18 passed
PYTHONPATH="src;../platform/src" python -m agridesk.app    # console on http://127.0.0.1:8000
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

- **It does not prescribe a pesticide dose.** It reports what surveillance shows and escalates.
- **It does not call a variant.** It links to a collapsed cluster produced by `clcuv-surveillance`.
- **It does not answer without evidence.** No dated source, no advisory — it escalates instead.
- **It does not need a connection.** Reports queue locally and reconcile on reconnect.

## Problems hit while building this

- Counting distinct sequences is not counting distinct variants, and the difference is an outbreak warning. This is `clcuv-surveillance`'s finding, reused rather than rediscovered.
- Collapsing on sequence alone was too aggressive across sites — the same sequence at two distant sites is two observations. Site is part of the key.

## Input / Output

Captured from a real run of this product — `scripts/capture.py` submits the payload below
through the HTTP surface, drains the queue, and approves. Every figure here came off a
machine.

**In** — `POST /intake`, keys: `claims`, `isolates`, `issued_receipts`, `since_day`

Published to `agri.tasks`; the call returns `202 {"status": "pending"}` with queue lag
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
| Result keys | `advisory.draft`, `branch_status`, `branches`, `branches_failed`, `claims`, `clusters`, `draft`, `drop_rate`, `dropped_claims`, `emerging`, `isolates`, `issued`, `issued_receipts`, `kept_claims`, `model`, `naive_count`, `since_day`, `summary`, `summary_subject` |

**The early exit**, on a payload that trips `no_emergence`:

| | |
|---|---|
| Status | `done` |
| Nodes visited | `triage` → `exit` |
| Model calls | **0** |

That last row is the one worth keeping. The cheap refusal costs nothing at all — no
gather, no generation — which is the whole reason it sits before the fan-out.
