import pytest

from shelfops.domain import FLOOR, PROMOTION, REPRICE, Proposal, compounded, decide, margin


def proposals():
    return [
        Proposal("repricer", REPRICE, 10.0),
        Proposal("promotions", PROMOTION, 15.0),
    ]


def test_the_deepest_single_proposal_wins():
    price = decide(10_000, proposals(), floor=1_000)
    assert price.value == 8_500
    assert price.applied.agent == "promotions"


def test_discounts_do_not_compound():
    # Two agents each writing the field would have produced 7,650.
    assert compounded(10_000, proposals()) == 7_650
    assert decide(10_000, proposals(), floor=1_000).value == 8_500


def test_the_rejected_proposals_are_recorded_not_discarded():
    price = decide(10_000, proposals(), floor=1_000)
    assert [p.agent for p in price.rejected] == ["repricer"]


def test_the_floor_is_absolute_and_binds():
    price = decide(10_000, [Proposal("clearance", "clearance", 90.0)], floor=5_000)
    assert price.value == 5_000
    assert price.at_floor
    assert price.reason == FLOOR


def test_no_proposals_leaves_the_price_alone():
    price = decide(10_000, [], floor=1_000)
    assert price.value == 10_000
    assert price.applied is None


def test_a_tie_resolves_by_agent_name_so_the_price_is_stable():
    tied = [Proposal("zeta", REPRICE, 20.0), Proposal("alpha", PROMOTION, 20.0)]
    assert decide(10_000, tied, floor=1).applied.agent == "alpha"
    assert decide(10_000, list(reversed(tied)), floor=1).applied.agent == "alpha"


def test_an_impossible_discount_is_refused():
    with pytest.raises(ValueError):
        Proposal("x", REPRICE, 120.0)


def test_a_floor_above_the_base_price_is_refused():
    with pytest.raises(ValueError):
        decide(1_000, [], floor=2_000)


def test_a_non_positive_base_is_refused():
    with pytest.raises(ValueError):
        decide(0, [], floor=1)


def test_margin_is_computed_not_narrated():
    assert margin(8_500, cost=6_000, fee_pct=12.0) == 8_500 - 6_000 - 1_020


def test_compounding_destroys_more_than_half_the_margin():
    # Both agents behaved correctly. One price authority nets 1,480 per unit;
    # two agents each writing the field net 732 — 50.5% of the margin gone,
    # with no bug in either agent.
    cost = 6_000
    authority = margin(decide(10_000, proposals(), floor=1).value, cost, 12.0)
    compounding = margin(compounded(10_000, proposals()), cost, 12.0)
    assert authority == 1_480
    assert compounding == 732
    assert compounding < authority / 2


def test_an_impossible_fee_is_refused():
    with pytest.raises(ValueError):
        margin(100, 10, 150.0)
