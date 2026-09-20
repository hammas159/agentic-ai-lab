# 08 · bid-desk

> Tender discovery, bid or no-bid, a compliance checklist that cannot be soft-passed, and a proposal drafted from work you won.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 20 proposal-forge and 23 market-desk; 25 web-operator becomes the crawler.

## The finding it exists to produce

Mandatory-item recall. A proposal missing one mandatory item is rejected unread, however
good the prose is. Measure recall on mandatory items specifically, and compare an LLM
extractor against a regex-plus-rulebook. The asymmetry — one miss is fatal, one false
positive costs ten minutes — is the whole design argument.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `crawler` | `tenders` (raw, plus a source snapshot) | a parsed requirement |
| `requirement-extractor` | `requirements`, each with a source span | an inferred requirement |
| `fit-scorer` | `fit_scores` from rules and a capability matrix | the bid/no-bid decision |
| `competitor-analyst` | `market_notes` with source dates | an undated claim |
| `proposal-writer` | `proposal_sections` | a capability claim absent from the capability store |
| `compliance-checker` | `checklist` pass or fail per item | a soft pass |

## Architecture

| Topic | Carries |
|---|---|
| `bid.intake` | everything arriving from outside |
| `bid.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `bid.events` | the audit trail, and what the projector and SSE stream read |
| `bid.approvals` | an agent needs a person; resumes a checkpointed graph |
| `bid.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:tender:{reference}` | the same tender is listed on three portals |
| `crawl:{domain}` | per-domain politeness, not a global rate |
| `lock:tender:{id}` | one extraction run per tender |
| `cache:fetch:{url}` | portals are slow and re-fetched across agents |

**Postgres:** `tenders, requirements, fit_scores, capabilities, proposal_sections, checklists, market_notes, events`.

**UI:** Flutter Web — a deadline board that also works on a phone, which is what a bid manager actually needs.

## Real data

**PPRA** public tenders (Pakistan), plus **TED** (EU) and **SAM.gov** (US) — all openly published with structured feeds.

## The deterministic core

`src/biddesk/domain.py` decides whether a bid is submittable at all, and how many days are left. Both are counting, not judgement. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not submit.** Submission is a human action, every time.
- **It does not soft-pass a mandatory item.** Missing is missing; the bid is blocked.
- **It does not claim a capability you cannot evidence.** Unbacked claims are dropped before drafting.
- **It does not cite an undated source.** Stale market numbers reported as current is the standard failure of this category.

## Problems hit while building this

- The deadline was first computed by the model, which got a month boundary wrong on a tender worth eight figures. It is date arithmetic now and always will be.
- 'Partially satisfied' was a category in the first checklist. It is not one on a tender portal, so it was removed — anything short of satisfied blocks the bid.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
