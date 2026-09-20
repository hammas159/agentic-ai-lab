"""What to do when the power goes, and what this process is allowed to touch.

The ownership rule is the important one. Other sessions train on this machine,
and a custodian that signals a PID it did not start is worse than no custodian.
"""

from __future__ import annotations

from dataclasses import dataclass

TRAINING = "training"
DOWNLOAD = "download"
OTHER = "other"

CHECKPOINT = "checkpoint"
PAUSE = "pause"
SLEEP_DISPLAYS = "sleep-displays"
HIBERNATE = "hibernate"
RESUME = "resume"


@dataclass(frozen=True)
class Job:
    pid: int
    name: str
    kind: str
    owned: bool          # started by this custodian
    checkpointable: bool = False
    resumable: bool = True


@dataclass(frozen=True)
class Machine:
    on_mains: bool
    battery_pct: int
    minutes_remaining: int

    def __post_init__(self) -> None:
        if not 0 <= self.battery_pct <= 100:
            raise ValueError("battery_pct must be a percentage")


@dataclass(frozen=True)
class Thresholds:
    hibernate_below_pct: int = 20
    hibernate_below_minutes: int = 5
    resume_above_pct: int = 35  # hysteresis: not the same line as hibernate

    def __post_init__(self) -> None:
        if self.resume_above_pct <= self.hibernate_below_pct:
            raise ValueError(
                "resume must sit above hibernate, or a flapping supply produces "
                "one action per flap"
            )


@dataclass(frozen=True)
class Action:
    verb: str
    target: str
    reason: str


# Cheapest to lose, last to be saved.
_COST = {TRAINING: 0, DOWNLOAD: 1, OTHER: 2}


def unowned_at_risk(jobs: list[Job]) -> list[Job]:
    """Jobs this custodian must not touch, and cannot protect.

    Surfaced so a person can act, never signalled. Another session's training
    run is not ours to stop.
    """
    return [j for j in jobs if not j.owned and j.kind in (TRAINING, DOWNLOAD)]


def plan(
    machine: Machine,
    jobs: list[Job],
    thresholds: Thresholds | None = None,
) -> list[Action]:
    """The ordered list of actions for the current power state."""
    t = thresholds or Thresholds()
    if machine.on_mains:
        return [
            Action(RESUME, j.name, "mains restored, battery above the resume line")
            for j in jobs
            if j.owned and j.resumable
        ] if machine.battery_pct >= t.resume_above_pct else []

    actions: list[Action] = []
    for job in sorted(jobs, key=lambda j: (_COST.get(j.kind, 9), j.pid)):
        if not job.owned:
            continue
        if job.kind == TRAINING and job.checkpointable:
            actions.append(
                Action(CHECKPOINT, job.name, "mains lost; an epoch is expensive")
            )
        elif job.kind == DOWNLOAD:
            actions.append(
                Action(
                    PAUSE,
                    job.name,
                    "mains lost; a partial transfer resumes, a dead one does not",
                )
            )

    actions.append(
        Action(SLEEP_DISPLAYS, "displays", "nothing is being watched on battery")
    )

    flat = machine.battery_pct <= t.hibernate_below_pct
    brief = machine.minutes_remaining <= t.hibernate_below_minutes
    if flat or brief:
        actions.append(
            Action(
                HIBERNATE,
                "system",
                f"battery {machine.battery_pct}%, "
                f"{machine.minutes_remaining} min left",
            )
        )
    return actions


def work_lost(gpu_hours: float, transferred_mb: int) -> dict:
    """The per-outage cost, for the before-and-after table."""
    if gpu_hours < 0 or transferred_mb < 0:
        raise ValueError("an outage cannot return work")
    return {"gpu_hours": round(gpu_hours, 2), "transferred_mb": transferred_mb}
