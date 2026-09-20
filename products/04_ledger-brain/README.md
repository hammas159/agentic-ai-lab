# 04 · ledger-brain

> SME back office: invoices in, bank statements in, reconciliation, inventory and cash flow out.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** the 'never let a model do arithmetic on money' lever from `BUILD-PLAN.md` 12 cloud-janitor.

## The finding it exists to produce

Equal amounts. When two open invoices are for the same value, a fuzzy or LLM matcher picks
one and is right half the time, silently. Measure matcher accuracy on the equal-amount
subset specifically — it will sit far below the headline number, and that subset is where
all the damage is.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `doc-intake` | `documents`, extracted fields with per-field confidence | a posted transaction |
| `reconciler` | `matches` where the deterministic matcher is unambiguous | an ambiguous match |
| `match-explainer` | `matches.rationale` | `matches.decision` |
| `inventory-watcher` | `reorder_suggestions` | a purchase order |
| `cashflow-analyst` | `projections` (computed) | a figure it did not compute |
| `collections-writer` | `chase_drafts` | sending |

## Architecture

| Topic | Carries |
|---|---|
| `fin.intake` | everything arriving from outside |
| `fin.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `fin.events` | the audit trail, and what the projector and SSE stream read |
| `fin.approvals` | an agent needs a person; resumes a checkpointed graph |
| `fin.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:doc:{sha256}` | the same invoice is photographed twice, constantly |
| `lock:invoice:{id}` | one reconciler per invoice |
| `cache:fx:{pair}:{day}` | rates are fetched once a day, not per row |
| `live:cash_position` | the dashboard figure |

**Postgres:** `documents, invoices, payments, matches, items, stock_moves, projections, events` — `events` is an immutable ledger of every posting.

**UI:** Django 5 + Tailwind, server-rendered — the right shape for a bookkeeping product, and the only server-rendered UI here.

## Real data

UCI Online Retail II for transaction history (a different angle from `csv-analyst`: inventory and cash flow, not revenue analysis), plus real invoice formats through `doc-intelligence-api`, which already parses CNIC, NTN, STRN and PK IBAN.

## The deterministic core

`src/ledger/domain.py` decides which payments match which invoices, and which matches are too ambiguous to make. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not post a journal entry on its own.** Every posting is a human action.
- **It does not let a model do arithmetic.** Numbers are computed in Python and quoted verbatim; a response containing a numeral absent from the tool output is rejected.
- **It does not guess between equal amounts.** It refuses and asks, which is the whole design.
- **It is not accounting software.** It reconciles and explains; it does not file anything.

## Problems hit while building this

- The first matcher scored 94% and looked finished. Splitting the metric by equal-amount versus distinct-amount is what showed where the errors actually were.
- Tolerance had to be absolute, not proportional. A 0.5% tolerance on a large invoice is wide enough to swallow a small one entirely.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
