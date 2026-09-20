import pytest

from ledger.domain import Invoice, Payment, equal_amount_subset, match, runway_days


def test_a_unique_amount_matches():
    out = match([Payment("p1", 12_000)], [Invoice("i1", 12_000), Invoice("i2", 9_900)])
    assert out.matched == {"p1": "i1"}


def test_two_invoices_at_the_same_amount_are_refused_not_guessed():
    out = match([Payment("p1", 12_000)], [Invoice("i1", 12_000), Invoice("i2", 12_000)])
    assert out.matched == {}
    assert out.ambiguous == {"p1": ["i1", "i2"]}


def test_a_reference_resolves_what_the_amount_cannot():
    out = match(
        [Payment("p1", 12_000, reference="INV-77")],
        [Invoice("i1", 12_000, reference="INV-77"), Invoice("i2", 12_000)],
    )
    assert out.matched == {"p1": "i1"}


def test_an_invoice_is_consumed_and_cannot_match_twice():
    out = match(
        [Payment("p1", 12_000), Payment("p2", 12_000)],
        [Invoice("i1", 12_000)],
    )
    assert out.matched == {"p1": "i1"}
    assert out.unmatched == ["p2"]


def test_a_payment_matching_nothing_is_unmatched():
    out = match([Payment("p1", 1)], [Invoice("i1", 12_000)])
    assert out.unmatched == ["p1"]


def test_tolerance_is_absolute_so_a_big_invoice_cannot_swallow_a_small_one():
    out = match(
        [Payment("p1", 1_000_050)],
        [Invoice("i1", 1_000_000), Invoice("i2", 50)],
        tolerance=100,
    )
    assert out.matched == {"p1": "i1"}


def test_a_negative_tolerance_is_refused():
    with pytest.raises(ValueError):
        match([], [], tolerance=-1)


def test_the_equal_amount_subset_is_reportable_on_its_own():
    invoices = [Invoice("i1", 100), Invoice("i2", 100), Invoice("i3", 250)]
    assert equal_amount_subset(invoices) == [100]


def test_ambiguity_rate_is_reported():
    out = match(
        [Payment("p1", 100), Payment("p2", 999)],
        [Invoice("i1", 100), Invoice("i2", 100)],
    )
    assert out.ambiguity_rate == pytest.approx(0.5)


def test_runway_is_whole_days_and_never_a_model_call():
    assert runway_days(1_000_000, 33_000) == 30


def test_runway_without_burn_is_undefined_rather_than_infinite():
    with pytest.raises(ValueError):
        runway_days(1_000, 0)
