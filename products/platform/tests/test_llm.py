import pytest

from agentplatform.admission import Controller, Gpu
from agentplatform.llm import (
    AdmissionRejectedError,
    Budgeted,
    Cached,
    Recorded,
    UnscriptedPromptError,
)
from agentplatform.ports import InMemoryCache


def model():
    return Recorded({"say hello": "hello there"})


def test_a_scripted_prompt_answers():
    completion = model().generate("say hello")
    assert completion.text == "hello there"
    assert completion.total_tokens == completion.prompt_tokens + completion.completion_tokens


def test_an_unscripted_prompt_raises_rather_than_inventing():
    # The property that keeps this package runnable with no model installed:
    # a test cannot quietly start calling ollama.
    with pytest.raises(UnscriptedPromptError):
        model().generate("what is the capital of France")


def test_the_cache_returns_the_second_call_without_the_model():
    inner = model()
    cached = Cached(inner, InMemoryCache())
    first = cached.generate("say hello")
    second = cached.generate("say hello")
    assert not first.cached
    assert second.cached
    assert len(inner.calls) == 1


def test_the_cache_key_does_not_contain_the_prompt():
    cache = InMemoryCache()
    Cached(model(), cache).generate("say hello")
    assert all("hello" not in k for k in cache._values)


def test_budget_refuses_before_the_model_is_touched():
    inner = model()
    budgeted = Budgeted(inner, Controller(Gpu(16384, 9000, 3000), {"acme": 1}), "acme")
    with pytest.raises(AdmissionRejectedError):
        budgeted.generate("say hello")
    assert inner.calls == []


def test_a_slot_is_released_after_a_successful_call():
    controller = Controller(Gpu(16384, 9000, 3000))
    budgeted = Budgeted(model(), controller)
    budgeted.generate("say hello")
    assert controller.in_flight == 0


def test_a_slot_is_released_even_when_the_model_raises():
    controller = Controller(Gpu(16384, 9000, 3000))
    budgeted = Budgeted(model(), controller)
    with pytest.raises(UnscriptedPromptError):
        budgeted.generate("unscripted")
    assert controller.in_flight == 0


def test_wrappers_keep_the_tag_so_results_record_which_model_ran():
    assert Cached(model(), InMemoryCache()).tag == "recorded"
