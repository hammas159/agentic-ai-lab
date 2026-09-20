# 10 · kyc-floor

> Customer onboarding, sanctions and PEP screening, and triage of the alerts screening produces.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** `BUILD-PLAN.md` 24 urdu-desk, which becomes the name-matching engine rather than a standalone project.

## The finding it exists to produce

`urdu-nlp-toolkit`'s finding promoted to a regulatory setting: the same name has several
byte encodings that render identically, and several defensible transliterations. Measure
**alias recall** on the sanctions lists — deterministic normalised matching against an LLM
asked 'are these the same person' — and publish the recall *and* the false-positive load at
the same threshold. A miss is a fine; a false-positive flood is an unstaffable queue.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `doc-verifier` | `identity.fields` with confidence | an approval |
| `name-matcher` | `screening_hits` — deterministic | a disposition |
| `alert-triager` | `alerts.disposition`, clear false positives only | clearing a true match |
| `media-researcher` | `media_findings` with source and date | an unsourced allegation |
| `filing-writer` | `sar.draft` | filing |
| `qa-sampler` | `qa_reviews` | overriding a human |

## Architecture

| Topic | Carries |
|---|---|
| `kyc.intake` | everything arriving from outside |
| `kyc.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `kyc.events` | the audit trail, and what the projector and SSE stream read |
| `kyc.approvals` | an agent needs a person; resumes a checkpointed graph |
| `kyc.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:{customer}:{list_version}` | a daily list refresh re-screens the whole book |
| `lock:alert:{id}` | one triager per alert |
| `index:names` | the in-memory screening index |
| `live:sla` | alert-ageing counters against the SLA |

**Postgres:** `customers, documents, identities, list_versions, screening_hits, alerts, media_findings, filings, events`.

**UI:** Next.js App Router — an alert queue, a four-quadrant match view, a filing composer.

## Real data

The **OFAC SDN list**, the **UN Consolidated Sanctions List** and the **EU list** — all publicly downloadable, all carrying alias fields, all full of the Arabic- and Urdu-origin names `urdu-nlp-toolkit` was written for.

## The deterministic core

`src/kycfloor/domain.py` decides whether two spellings are the same name. Nothing about that is language understanding; it is normalisation. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not onboard a customer.** It screens and triages; a human approves.
- **It does not clear a true match.** The triager may dispose of clear false positives and nothing else.
- **It does not file a SAR.** Draft only.
- **It does not score risk with a model.** A published matrix, so a regulator can read it.
- **It does not match names with an LLM.** That is the baseline it is measured against, not the implementation.

## Problems hit while building this

- Stripping every non-letter merged `al-Hassan` and `Alhassan` correctly and also merged two genuinely different names. Particle handling is separate from diacritic handling for that reason.
- Token *order* varies between lists — `Khan Ayesha` and `Ayesha Khan` are the same person. Comparison is over sets, which then required a minimum token count so single-token names do not match everything.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
