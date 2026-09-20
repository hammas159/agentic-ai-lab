"""powerguard against this machine.

Not a fixture: real processes, the real GPU, the real power state. The
assertions are written as properties rather than frozen counts, because what is
running changes — except where a count is the finding.
"""

import pytest

from powerguard.domain import DOWNLOAD, OTHER, TRAINING, Machine, plan, unowned_at_risk
from powerguard.machine import Process, gpu, jobs, power, processes

HERE = processes()
pytestmark = pytest.mark.skipif(not HERE, reason="cannot read processes on this host")


def test_the_machine_is_readable():
    assert len(HERE) > 50
    # pid 0 is real on Windows: the System Idle Process.
    assert all(p.pid >= 0 for p in HERE)
    assert any(p.pid > 0 for p in HERE)


def test_the_power_state_is_read_not_assumed():
    m = power()
    assert isinstance(m, Machine)
    assert 0 <= m.battery_pct <= 100
    # A desktop reports no battery. That is a machine hibernating cannot save,
    # and the honest reading is "on mains", not an error.


def test_the_card_is_read_if_there_is_one():
    card = gpu()
    if card is None:
        pytest.skip("no nvidia-smi on this host")
    assert card.total_mb > 0
    assert 0 <= card.used_mb <= card.total_mb
    assert card.free_mb == card.total_mb - card.used_mb


def test_the_interpreter_install_path_is_not_a_classification_signal():
    # THE BUG THIS CAUGHT. Matching the raw command line classified every Python
    # process here as a download, because the interpreter lives under
    # ...\AppData\Roaming\uv\python\... and "\buv\b" matches inside a path.
    # It took 14 "expensive jobs" down to 3 once fixed.
    noise = Process(
        pid=1,
        name="python.exe",
        command=r"C:\Users\x\AppData\Roaming\uv\python\cpython-3.12\python.exe script.py",
    )
    assert noise.kind == OTHER

    real = Process(pid=2, name="uv.exe", command="uv pip install torch")
    assert real.kind == DOWNLOAD


def test_a_training_run_is_recognised_by_its_arguments():
    assert Process(pid=3, name="python.exe", command="python train_shr.py").kind == TRAINING
    assert Process(pid=4, name="python.exe", command="python -m pytest -q").kind == TRAINING


def test_the_signature_discards_the_executable_path():
    p = Process(pid=5, name="x", command=r'"C:\Program Files\ollama\ollama.exe" serve')
    assert p.signature == "ollama.exe serve"
    assert p.kind == DOWNLOAD


def test_expensive_work_is_a_small_fraction_of_what_is_running():
    found = jobs()
    assert len(found) < len(HERE) / 10  # most of a machine is not doing work worth saving


def test_it_never_plans_an_action_on_a_process_it_does_not_own():
    # THE FINDING. On this shared machine the expensive work belongs to other
    # sessions, so the custodian reports it and reaches for none of it.
    #
    # Note what this test caught about itself: run under pytest, `jobs()`
    # includes the pytest process, owned by this very run. So the assertion is
    # not "everything is someone else's" — it is the property that actually
    # matters, which holds either way.
    found = jobs()
    unowned = unowned_at_risk(found)
    assert unowned, "expected at least one job belonging to another session"

    actions = plan(Machine(on_mains=False, battery_pct=40, minutes_remaining=25), found)
    # Identity is the pid, never the name. Two sessions both run python.exe,
    # and this test failed on exactly that before Action carried a pid.
    touched = {a.pid for a in actions if a.pid is not None}
    for job in unowned:
        assert job.pid not in touched


def test_the_ollama_server_is_visible_and_untouchable():
    # Concrete: the model server holding 9 GB of this card was started by
    # another session. It is exactly what an outage would destroy, and exactly
    # what this custodian must not signal.
    found = jobs()
    theirs = {j.name for j in unowned_at_risk(found)}
    assert any("ollama" in name.lower() or "llama" in name.lower() for name in theirs)


def test_it_still_sleeps_what_it_does_own():
    # Displays are not a process. Losing mains always sleeps them.
    actions = plan(Machine(on_mains=False, battery_pct=90, minutes_remaining=60), jobs())
    assert any(a.target == "displays" for a in actions)
