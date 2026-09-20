# 19 · agri-desk

> Crop advisory over your own surveillance data, offline first, with an explicit escalation path.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

`clcuv-surveillance` found that collapsing clonal duplicates turned **9 'emerging variants'
into 0** — the signal was one isolate sequenced repeatedly. An advisory agent reading the
uncollapsed feed will warn about an outbreak that does not exist. Measure the false-alarm
rate on the same data, collapsed and uncollapsed.

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

## What it does NOT do

- **It does not prescribe a pesticide dose.** It reports what surveillance shows and escalates.
- **It does not call a variant.** It links to a collapsed cluster produced by `clcuv-surveillance`.
- **It does not answer without evidence.** No dated source, no advisory — it escalates instead.
- **It does not need a connection.** Reports queue locally and reconcile on reconnect.

## Problems hit while building this

- Counting distinct sequences is not counting distinct variants, and the difference is an outbreak warning. This is `clcuv-surveillance`'s finding, reused rather than rediscovered.
- Collapsing on sequence alone was too aggressive across sites — the same sequence at two distant sites is two observations. Site is part of the key.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
