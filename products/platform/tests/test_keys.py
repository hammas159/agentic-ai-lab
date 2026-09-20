from datetime import date

import pytest

from agentplatform import keys


def test_every_key_carries_its_expiry():
    assert keys.ctx("run_7f3a91") == keys.Key("ctx:run_7f3a91", keys.HOUR)
    assert keys.idem("gmail", "msg_9a1").ttl_seconds == keys.DAY


def test_lock_ttl_is_short_by_construction():
    assert keys.lock("deal", "4192").ttl_seconds == 60


def test_a_long_lock_is_refused_rather_than_allowed():
    with pytest.raises(ValueError):
        keys.lock("deal", "4192", ttl_seconds=600)


def test_budget_is_scoped_to_a_day():
    k = keys.budget("acme", date(2026, 9, 20))
    assert k.name == "budget:acme:2026-09-20"


def test_the_prompt_is_hashed_and_not_stored():
    k = keys.llmcache("qwen2.5:14b-instruct", "who is the CFO of Acme")
    assert "Acme" not in k.name
    assert k.name.startswith("llmcache:")
    assert len(k.name.split(":")[1]) == 64


def test_the_same_prompt_on_two_models_is_two_cache_entries():
    a = keys.llmcache("qwen2.5:7b-instruct", "hello")
    b = keys.llmcache("qwen2.5:14b-instruct", "hello")
    assert a != b


def test_live_counters_do_not_expire():
    assert keys.live("floor").ttl_seconds is None
