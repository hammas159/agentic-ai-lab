import pytest

from revenue.domain import (
    Deal,
    Edit,
    UnknownStageError,
    detect_reverts,
    revert_rate,
    weighted_forecast,
)


def deals():
    return [
        Deal("d1", 4_200_000, "sourced"),
        Deal("d2", 6_400_000, "qualified"),
        Deal("d3", 8_800_000, "proposal"),
        Deal("d4", 7_100_000, "closing"),
    ]


def test_forecast_is_arithmetic_and_reproducible():
    first = weighted_forecast(deals())
    assert first == weighted_forecast(deals())
    assert first == round(
        4_200_000 * 0.05 + 6_400_000 * 0.20 + 8_800_000 * 0.50 + 7_100_000 * 0.80, 2
    )


def test_a_lost_deal_contributes_nothing():
    assert weighted_forecast([Deal("d", 1_000_000, "lost")]) == 0.0


def test_an_unknown_stage_is_refused_rather_than_guessed():
    with pytest.raises(UnknownStageError):
        weighted_forecast([Deal("d", 1, "renegotiation")])


def test_a_negative_amount_is_a_bug_not_a_credit():
    with pytest.raises(ValueError):
        weighted_forecast([Deal("d", -1, "closing")])


def test_an_agent_overwriting_a_human_is_a_revert():
    edits = [
        Edit(1, "deal.close_date", "2026-10-28", "human"),
        Edit(2, "deal.close_date", "2026-10-14", "deal-analyst"),
    ]
    (revert,) = detect_reverts(edits)
    assert revert.by == "deal-analyst"
    assert revert.human_value == "2026-10-28"


def test_an_agent_correcting_another_agent_is_not_a_revert():
    edits = [
        Edit(1, "company.headcount", 800, "enricher"),
        Edit(2, "company.headcount", 900, "enricher"),
    ]
    assert detect_reverts(edits) == []


def test_writing_the_same_value_a_human_chose_is_not_a_revert():
    edits = [
        Edit(1, "deal.amount", 100, "human"),
        Edit(2, "deal.amount", 100, "deal-analyst"),
    ]
    assert detect_reverts(edits) == []


def test_the_human_must_be_the_most_recent_prior_edit():
    edits = [
        Edit(1, "deal.amount", 100, "human"),
        Edit(2, "deal.amount", 200, "analyst"),
        Edit(3, "deal.amount", 300, "analyst"),
    ]
    # Only the first agent edit reverted a person; the second overwrote an agent.
    assert len(detect_reverts(edits)) == 1


def test_order_comes_from_the_sequence_not_the_list():
    edits = [
        Edit(2, "deal.amount", 200, "analyst"),
        Edit(1, "deal.amount", 100, "human"),
    ]
    assert len(detect_reverts(edits)) == 1


def test_revert_rate_is_over_agent_edits_only():
    edits = [
        Edit(1, "a", 1, "human"),
        Edit(2, "a", 2, "analyst"),
        Edit(3, "b", 1, "analyst"),
    ]
    assert revert_rate(edits) == pytest.approx(0.5)


def test_a_run_with_no_agent_edits_has_no_rate_rather_than_dividing_by_zero():
    assert revert_rate([Edit(1, "a", 1, "human")]) == 0.0
