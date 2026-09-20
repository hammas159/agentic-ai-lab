# 12 · powerguard

> Machine custodian: on mains loss, checkpoint the training run, pause the downloads, sleep the displays, hibernate before the battery goes.

**Status:** scaffold. The deterministic core is written and tested. The agents, the UI and
the wiring are not built yet.

## The finding it exists to produce

Work lost per outage, before and after. The baseline is already on this machine and is not
theoretical: five dead model pulls and a training run paused at epoch 18 of 30. Count the
GPU-hours and the transferred bytes destroyed per power event, then count them again with a
custodian running.

## Agents and write authority

Enforced by `agentplatform.authority`, which is default-deny — a field nobody was granted
is closed, so a column added next month does not quietly become writable.

| Agent | May write | Never |
|---|---|---|
| `sensor-watcher` | `readings` — polled, never inferred | any action |
| `policy-engine` | `plans` — deterministic, no model | executing a plan |
| `job-custodian` | signals to processes **it started** | any PID it does not own |
| `resume-planner` | `resume_order` from the dependency graph | starting a job a person disabled |
| `incident-narrator` | `events.summary` — the only model call here | a figure it did not read |

## Architecture

| Topic | Carries |
|---|---|
| `power.intake` | everything arriving from outside |
| `power.tasks` | work for the agent workers; group size is set by VRAM, not partitions |
| `power.events` | the audit trail, and what the projector and SSE stream read |
| `power.approvals` | an agent needs a person; resumes a checkpointed graph |
| `power.dlq` | a consumer gave up; a human looks at it |

| Redis key | Purpose |
|---|---|
| `live:power` | mains, battery and runtime, read by the tray every second |
| `owned:{pid}` | the ownership registry — the only PIDs this may signal |
| `lock:plan` | one custodian acting at a time |
| `idem:event:{id}` | a flapping supply emits the same transition repeatedly |

**Postgres:** `readings, jobs, plans, actions, outages, events` — `outages` is what the finding is computed from.

**UI:** A system-tray applet with a timeline page — the only honest shape for something that has to work while the screen is off.

## Real data

This machine. UPS or battery state via the OS, GPU load via `nvidia-smi`, and the real job table: model pulls, training runs, prefetches.

## The deterministic core

`src/powerguard/domain.py` decides what to do when the power goes, in what order, and — above all — which processes it is allowed to touch. It is here rather than in a prompt because it is
arithmetic, matching or a rule — not language work. The model's job is to write the
sentence around the answer, never to produce the answer.

```
PYTHONPATH=src python -m pytest -q
```

## What it does NOT do

- **It never signals a process it did not start.** Other chat sessions train on this box. Unowned jobs at risk are reported to you and left alone. This is enforced in the planner, not in a comment.
- **It does not decide policy with a model.** Thresholds are numbers in a config file.
- **It does not force-kill.** Checkpoint, then request a stop, then wait. A `TaskStop` that does not kill a process tree is a known behaviour here, not a surprise.
- **It does not resume a job you disabled**, however idle the machine gets.

## Problems hit while building this

- The obvious first version shut things down in whatever order it found them, which put the display to sleep before the training checkpoint had flushed. The plan is ordered by how much work each step saves, cheapest to lose last.
- Hibernate needs a threshold with hysteresis. A supply that flaps either side of the line otherwise produces an action per flap.

## Input / Output

Nothing measured yet. No number appears in this README that was not produced on a machine,
and so far this product has produced none. The first one it owes is the finding above.
