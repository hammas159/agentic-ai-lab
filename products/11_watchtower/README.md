# 11 · watchtower

> Vulnerability, exposure and configuration-drift agent for the machines you are authorised to scan.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Version-string CVE matching is mostly false positives, because distributions backport a
fix without bumping the upstream version. Measure the false-positive rate on a real host,
then again once the backport table is consulted. The gap is the entire value of the
product, and it is the reason a raw scanner output is ignored after week two.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `inventory` | `assets`, `packages` — collected, never inferred | a vulnerability verdict |
| `cve-matcher` | `findings` — deterministic version comparison | an exploitability judgement |
| `exploitability-triager` | `findings.priority`, with the reachability evidence | closing a finding |
| `remediation-writer` | `remediations.draft` | applying a change |
| `exception-approver` | nothing — a human owns this | everything |

## Architecture

| Topic | Carries |
|---|---|
| `sec.intake` | everything arriving from outside |
| `sec.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `sec.events` | the audit trail, and what the projector and SSE stream read |
| `sec.approvals` | an agent needs a person; resumes a checkpointed graph |
| `sec.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `lock:host:{id}` | one scan per host; a second scan is not twice as good |
| `cache:nvd:{cve}` | the advisory feed is refetched by every worker otherwise |
| `idem:scan:{host}:{feed_version}` | a feed refresh re-screens the estate |
| `live:posture` | the board's counters |

**Postgres:** `assets, packages, feeds, advisories, findings, remediations, exceptions, events`.

**UI:** Textual TUI for the box you are logged into, plus a read-only web board for everything else.

## Real data

This machine and any host you own, plus the public NVD feed and the distribution security trackers. **Scope is a file, and the scanner cannot run outside it** — that is enforced in code, not in a README.

## The deterministic core

`src/watchtower/domain.py` decides whether an installed version is actually vulnerable, and whether a host is in scope at all. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not scan anything outside its scope file.** Out-of-scope targets are refused, not warned about.
- **It does not exploit.** No payload, no proof-of-concept execution. It reports what is present and reachable.
- **It does not patch.** Remediations are drafted; a person applies them.
- **It does not trust a version string alone.** That is the finding.
- **It is not a pentest tool.** It is an inventory-and-advisory reconciler for estates you own.

## Problems hit while building this

- The first matcher compared version strings lexically, which put `1.10.0` below `1.9.0`. Parsing into integer components is not optional.
- Distribution suffixes (`-4ubuntu1.2`) are the whole backport signal, and stripping them — which is what makes the upstream comparison clean — is exactly what destroys the information needed to avoid a false positive.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
