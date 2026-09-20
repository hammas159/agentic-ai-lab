# 16 · shelf-ops

> Marketplace operations: catalogue, repricing, promotions, returns triage and supplier chasing, with one price authority.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

The repricer and the promotions agent compound each other's discounts. Measure realised
margin with a single price authority against two agents that each believe they own the
field. The failure needs no bug in either agent — both behave correctly alone.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `listing-writer` | `listings.draft` | a published listing |
| `repricer` | `price_proposals` | `listings.price` directly |
| `promotions-planner` | `price_proposals` | `listings.price` directly |
| `price-authority` | `listings.price` — the only writer, deterministic | going below the floor |
| `returns-classifier` | `returns.reason` | issuing a refund |
| `supplier-chaser` | `chase_drafts` | sending |

## Architecture

| Topic | Carries |
|---|---|
| `shelf.intake` | everything arriving from outside |
| `shelf.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `shelf.events` | the audit trail, and what the projector and SSE stream read |
| `shelf.approvals` | an agent needs a person; resumes a checkpointed graph |
| `shelf.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:sku:{id}` | per-SKU ordering, which is why the bus is keyed on SKU |
| `cache:competitor:{sku}` | competitor prices are polled, not fetched per proposal |
| `idem:order:{marketplace}:{id}` | marketplaces redeliver order webhooks |
| `live:margin` | the board's realised-margin counter |

**Postgres:** `skus, listings, price_proposals, price_history, orders, returns, suppliers, events`.

**UI:** SolidStart, or an Electron workstation for a warehouse desk that is open all day.

## Real data

UCI Online Retail II for order history, and published marketplace fee schedules, which are real and openly available. Competitor prices are polled from sites that permit it.

## The deterministic core

`src/shelfops/domain.py` decides the final price, from every proposal at once, with a hard floor. Discounts never compound. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not let an agent write a price.** Agents propose; one deterministic authority decides.
- **It does not compound discounts.** The deepest single proposal wins and the floor is absolute.
- **It does not issue refunds.** Returns are classified and routed.
- **It does not scrape a marketplace that forbids it.** Feeds and APIs where they exist.

## Problems hit while building this

- Both agents were correct in isolation and the system was not. Nothing in either prompt could have fixed it; the fix is that only one component writes the field.
- A percentage floor was the first design and it is wrong on a low-margin SKU — 10% off a product carrying 8% margin is a loss whatever the floor says. The floor is an absolute price.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
