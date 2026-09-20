import pytest

from agentplatform.admission import Controller, Gpu


def quadro() -> Gpu:
    # Quadro RTX 5000, 16 GB, a 14B at Q4 and 3 GB of KV cache per slot.
    return Gpu(total_mb=16384, model_mb=9000, kv_cache_mb_per_slot=3000)


def test_slots_come_from_vram_not_from_partition_count():
    assert quadro().max_slots == 2


def test_a_card_that_barely_fits_the_model_still_gets_one_slot():
    assert Gpu(total_mb=10000, model_mb=9000, kv_cache_mb_per_slot=3000).max_slots == 1


def test_a_model_that_does_not_fit_is_refused_up_front():
    with pytest.raises(ValueError):
        Gpu(total_mb=8000, model_mb=9000, kv_cache_mb_per_slot=3000)


def test_admission_stops_at_the_slot_count():
    c = Controller(quadro())
    assert c.admit("acme", 500).admitted
    assert c.admit("acme", 500).admitted
    third = c.admit("acme", 500)
    assert not third.admitted
    assert "slots busy" in third.reason


def test_releasing_frees_a_slot():
    c = Controller(quadro())
    c.admit("acme", 1)
    c.admit("acme", 1)
    c.release()
    assert c.admit("acme", 1).admitted


def test_budget_is_checked_before_the_gpu_is_touched():
    c = Controller(quadro(), daily_token_budget={"acme": 1000})
    assert c.admit("acme", 900).admitted
    refused = c.admit("acme", 200)
    assert not refused.admitted
    assert "daily budget" in refused.reason
    assert c.in_flight == 1  # the refused request never took a slot


def test_a_tenant_with_no_budget_is_unlimited():
    c = Controller(quadro(), daily_token_budget={"acme": 10})
    assert c.admit("other", 10_000).admitted


def test_releasing_more_than_was_admitted_is_a_bug_not_a_shrug():
    with pytest.raises(RuntimeError):
        Controller(quadro()).release()
