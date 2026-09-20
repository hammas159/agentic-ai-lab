import pytest

from driftwatch.domain import (
    JUDGEMENT,
    MECHANICAL,
    NOT_CHECKABLE,
    Claim,
    broken,
    verifiable_share,
    verify,
)


def test_a_version_claim_is_mechanical():
    assert Claim("Requires Python >= 3.11").kind == MECHANICAL


def test_a_test_count_claim_is_mechanical():
    assert Claim("376 tests, all passing").kind == MECHANICAL


def test_a_dependency_claim_is_mechanical():
    assert Claim("Zero runtime dependencies.").kind == MECHANICAL


def test_an_adjective_is_not_a_claim_a_machine_can_settle():
    assert Claim("Fast, simple and production-ready.").kind == JUDGEMENT


def test_an_unfalsifiable_claim_is_reported_not_rewritten():
    verdict = verify(Claim("Blazingly fast."), {})
    assert not verdict.checked
    assert verdict.holds is None
    assert verdict.detail == NOT_CHECKABLE


def test_a_matching_version_claim_holds():
    assert verify(Claim("Requires Python >= 3.11"), {"requires_python": ">=3.11"}).holds


def test_a_stale_version_claim_does_not_hold():
    verdict = verify(Claim("Requires Python >= 3.9"), {"requires_python": ">=3.11"})
    assert verdict.checked
    assert verdict.holds is False


def test_a_test_count_is_compared_against_the_collected_count():
    # Collected exceeds `def test_` wherever parametrize is used, which is why
    # the fact is named collected_tests.
    assert verify(Claim("376 tests"), {"collected_tests": 376}).holds
    assert verify(Claim("376 tests"), {"collected_tests": 402}).holds is False


def test_a_thousands_separator_does_not_break_the_count():
    assert verify(Claim("2,084 tests"), {"collected_tests": 2084}).holds


def test_a_missing_fact_means_unchecked_rather_than_failed():
    verdict = verify(Claim("376 tests"), {})
    assert not verdict.checked
    assert verdict.holds is None


def test_a_zero_dependency_claim_is_checked_against_the_declared_list():
    assert verify(Claim("Zero runtime dependencies."), {"dependencies": []}).holds
    declared = verify(Claim("Zero runtime dependencies."), {"dependencies": ["httpx"]})
    assert declared.holds is False


def test_the_verifiable_share_is_the_headline_ratio():
    claims = [Claim("Requires Python >= 3.11"), Claim("Fast."), Claim("Simple.")]
    assert verifiable_share(claims) == pytest.approx(1 / 3)


def test_an_empty_readme_has_no_ratio_rather_than_dividing_by_zero():
    assert verifiable_share([]) == 0.0


def test_only_checked_and_failing_claims_reach_the_pull_request():
    verdicts = [
        verify(Claim("Requires Python >= 3.9"), {"requires_python": ">=3.11"}),
        verify(Claim("Blazingly fast."), {}),
        verify(Claim("Zero runtime dependencies."), {"dependencies": []}),
    ]
    assert len(broken(verdicts)) == 1
