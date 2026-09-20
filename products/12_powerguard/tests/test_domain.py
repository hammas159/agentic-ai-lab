import pytest

from powerguard.domain import (
    CHECKPOINT,
    DOWNLOAD,
    HIBERNATE,
    PAUSE,
    RESUME,
    SLEEP_DISPLAYS,
    TRAINING,
    Job,
    Machine,
    Thresholds,
    plan,
    unowned_at_risk,
    work_lost,
)


def jobs():
    return [
        Job(101, "train_shr", TRAINING, owned=True, checkpointable=True),
        Job(202, "ollama pull qwen2.5:14b-instruct", DOWNLOAD, owned=True),
        Job(303, "someone-elses-train", TRAINING, owned=False, checkpointable=True),
    ]


def test_on_battery_the_training_run_is_checkpointed_first():
    actions = plan(Machine(on_mains=False, battery_pct=80, minutes_remaining=40), jobs())
    assert actions[0].verb == CHECKPOINT
    assert actions[0].target == "train_shr"


def test_downloads_are_paused_not_killed():
    actions = plan(Machine(on_mains=False, battery_pct=80, minutes_remaining=40), jobs())
    verbs = {(a.verb, a.target) for a in actions}
    assert (PAUSE, "ollama pull qwen2.5:14b-instruct") in verbs


def test_it_never_acts_on_a_process_it_did_not_start():
    actions = plan(Machine(on_mains=False, battery_pct=10, minutes_remaining=2), jobs())
    assert all(a.target != "someone-elses-train" for a in actions)


def test_unowned_jobs_at_risk_are_reported_instead():
    at_risk = unowned_at_risk(jobs())
    assert [j.pid for j in at_risk] == [303]


def test_displays_sleep_once_on_battery():
    actions = plan(Machine(on_mains=False, battery_pct=90, minutes_remaining=60), jobs())
    assert sum(1 for a in actions if a.verb == SLEEP_DISPLAYS) == 1


def test_a_healthy_battery_does_not_hibernate():
    actions = plan(Machine(on_mains=False, battery_pct=90, minutes_remaining=60), jobs())
    assert all(a.verb != HIBERNATE for a in actions)


def test_a_low_battery_hibernates_last():
    actions = plan(Machine(on_mains=False, battery_pct=15, minutes_remaining=30), jobs())
    assert actions[-1].verb == HIBERNATE


def test_low_minutes_hibernate_even_at_a_healthy_percentage():
    # A worn battery reports 60% and four minutes. The percentage lies.
    actions = plan(Machine(on_mains=False, battery_pct=60, minutes_remaining=4), jobs())
    assert actions[-1].verb == HIBERNATE


def test_mains_restored_resumes_owned_jobs_only():
    actions = plan(Machine(on_mains=True, battery_pct=80, minutes_remaining=120), jobs())
    assert {a.verb for a in actions} == {RESUME}
    assert all(a.target != "someone-elses-train" for a in actions)


def test_mains_restored_on_a_flat_battery_does_not_resume_yet():
    assert plan(Machine(on_mains=True, battery_pct=22, minutes_remaining=10), jobs()) == []


def test_the_hysteresis_gap_is_required_not_optional():
    with pytest.raises(ValueError):
        Thresholds(hibernate_below_pct=30, resume_above_pct=30)


def test_an_impossible_battery_reading_is_refused():
    with pytest.raises(ValueError):
        Machine(on_mains=False, battery_pct=140, minutes_remaining=10)


def test_work_lost_is_counted_not_estimated():
    assert work_lost(3.5, 8571) == {"gpu_hours": 3.5, "transferred_mb": 8571}


def test_an_outage_cannot_return_work():
    with pytest.raises(ValueError):
        work_lost(-1, 0)
