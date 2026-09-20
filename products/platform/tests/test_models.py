import pytest

from agentplatform.models import (
    GENERAL,
    NoModelForRoleError,
    comparison_pending,
    resolve,
)

INSTALLED_TODAY = [
    "qwen2.5-coder:14b",
    "qwen2.5:7b-instruct",
    "qwen2.5:3b-instruct",
    "llama3.2:3b",
    "nomic-embed-text:latest",
]


def test_the_best_installed_model_wins():
    assert resolve(GENERAL, INSTALLED_TODAY).tag == "qwen2.5:7b-instruct"


def test_a_missing_preferred_model_does_not_block_the_product():
    chosen = resolve(GENERAL, INSTALLED_TODAY)
    assert not chosen.is_preferred
    assert "standing in for qwen2.5:14b-instruct" in chosen.note


def test_the_preferred_model_is_used_once_it_lands():
    chosen = resolve(GENERAL, [*INSTALLED_TODAY, "qwen2.5:14b-instruct"])
    assert chosen.tag == "qwen2.5:14b-instruct"
    assert chosen.is_preferred


def test_the_pending_comparison_row_is_nameable():
    assert comparison_pending(GENERAL, INSTALLED_TODAY) == "qwen2.5:14b-instruct"
    assert comparison_pending(GENERAL, [*INSTALLED_TODAY, "qwen2.5:14b-instruct"]) is None


def test_a_coder_role_resolves_to_the_coder_model():
    assert resolve("coder", INSTALLED_TODAY).tag == "qwen2.5-coder:14b"


def test_an_unknown_role_is_refused():
    with pytest.raises(NoModelForRoleError):
        resolve("oracle", INSTALLED_TODAY)


def test_an_empty_machine_is_refused_with_the_options_named():
    with pytest.raises(NoModelForRoleError, match="qwen2.5:14b-instruct"):
        resolve(GENERAL, [])
