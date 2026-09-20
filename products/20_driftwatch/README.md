# 20 · driftwatch

> Watches a repository for the moment its documentation stops being true, and opens the pull request that fixes it.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

**Absorbs:** the priority-70 code–doc staleness item from the SWE queue. Distinct from the shipped `docstring-drift`, which measures the phenomenon; this one repairs it continuously.

## The finding it exists to produce

What share of documentation drift is *mechanically verifiable* rather than a matter of
judgement. `compliance-auditor` already found the most confidently stated house convention
holds in 9 of 33 repos. Split the claims a README makes into checkable and unfalsifiable,
and report the ratio — most doc-linting tools assume the first category is all there is.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `change-watcher` | `changes` from webhooks | a claim |
| `claim-extractor` | `claims` with a file and line | a verdict |
| `verifier` | `verdicts` — executed, never reasoned | a verdict on an unfalsifiable claim |
| `patch-writer` | `patches.draft` | committing |
| `pr-opener` | a pull request, on approval | merging |

## Architecture

| Topic | Carries |
|---|---|
| `drift.intake` | everything arriving from outside |
| `drift.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `drift.events` | the audit trail, and what the projector and SSE stream read |
| `drift.approvals` | an agent needs a person; resumes a checkpointed graph |
| `drift.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `idem:delivery:{webhook_id}` | GitHub redelivers webhooks |
| `lock:repo:{id}` | one verification run per repository |
| `cache:facts:{sha}` | repository facts are re-derived per claim otherwise |
| `budget:{repo}:{day}` | a monorepo can exhaust a day of tokens |

**Postgres:** `repos, changes, claims, verdicts, patches, pulls, events`.

**UI:** Astro with React islands — a docs-shaped product deserves a docs-shaped site.

## Real data

The 33 repositories already on this machine and their real READMEs. `compliance-auditor` has already run over them and produced the 9-of-33 figure this product starts from.

## The deterministic core

`src/driftwatch/domain.py` decides which documentation claims can be checked by running something, and which cannot. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It does not merge.** It opens a pull request; a person merges.
- **It does not rewrite prose it cannot check.** An unfalsifiable claim is reported to a human, never silently edited.
- **It does not reason about a claim.** Mechanical claims are executed against the repository.
- **It does not replace `docstring-drift`.** That repository measured the phenomenon; this one repairs it.

## Problems hit while building this

- The first extractor treated every sentence as a claim and produced a wall of unfalsifiable findings — 'fast', 'simple', 'production-ready' — which is exactly the noise that gets a doc linter turned off. Classification comes first now.
- A test-count claim needs the count collected, not the `def test_` lines counted: parametrised tests make the two differ, which `PROJECTS.md` already records.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
