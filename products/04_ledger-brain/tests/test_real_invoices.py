"""ledger-brain against 54,716 real invoices.

`products/data/invoices.csv` is derived once from UCI's Online Retail II by
`scripts/make_invoices.py`. Every figure asserted here was produced by running
this code over that file.
"""

import pytest

from ledger.domain import Payment, match
from ledger.invoices import (
    LEDGER,
    as_invoices,
    collisions,
    headline_accuracy,
    read,
    receivables,
)

pytestmark = pytest.mark.skipif(not LEDGER.exists(), reason="invoice extract not built")


@pytest.fixture(scope="module")
def rows():
    return read()


@pytest.fixture(scope="module")
def bills(rows):
    return receivables()


def test_the_ledger_loads(rows):
    assert len(rows) == 54_716
    assert all(isinstance(r.amount, int) for r in rows)


def test_cancellations_net_to_exactly_zero(rows):
    zeros = [r for r in rows if r.nets_to_zero]
    assert len(zeros) == 5_372
    # Every one of them collides with every other, which is why they are
    # excluded from the receivables population rather than left to flatter it.


def test_half_of_real_invoices_share_their_amount_with_another(bills):
    # THE FINDING. Not an edge case, not a tail: half the population.
    c = collisions(bills)
    assert c.population == 40_912
    assert c.collision_rate == pytest.approx(0.509, abs=0.01)
    assert c.colliding_amounts == 7_006


def test_an_amount_only_matcher_is_a_coin_toss_on_that_half(bills):
    c = collisions(bills)
    assert c.guess_accuracy == pytest.approx(0.337, abs=0.01)


def test_the_headline_hides_it_completely(bills):
    # 66% overall looks like a matcher that mostly works. It is the average of
    # "always right on the unique half" and "wrong two times in three on the
    # other half", and only the second half does any damage.
    assert headline_accuracy(bills) == pytest.approx(0.663, abs=0.01)


def test_the_worst_collision_is_large(bills):
    assert collisions(bills).largest_group == 126  # £15.00, 126 times


def test_including_credits_makes_the_number_look_worse_than_it_is(rows):
    everything = collisions(list(rows))
    just_bills = collisions(receivables())
    assert everything.collision_rate > just_bills.collision_rate
    assert everything.collision_rate == pytest.approx(0.599, abs=0.01)


def test_the_matcher_refuses_a_real_collision(bills):
    from collections import Counter

    amounts = Counter(r.amount for r in bills)
    tied = next(a for a, n in amounts.most_common() if n > 1)
    candidates = [r for r in bills if r.amount == tied][:2]

    out = match([Payment("p1", tied)], as_invoices(candidates))
    assert out.matched == {}
    assert sorted(out.ambiguous["p1"]) == sorted(r.invoice for r in candidates)


def test_the_matcher_still_settles_a_unique_amount(bills):
    from collections import Counter

    amounts = Counter(r.amount for r in bills)
    unique = next(a for a, n in amounts.items() if n == 1)
    only = next(r for r in bills if r.amount == unique)

    out = match([Payment("p1", unique)], as_invoices([only]))
    assert out.matched == {"p1": only.invoice}


def test_a_missing_ledger_is_reported_rather_than_faked():
    from ledger.invoices import LedgerMissingError

    with pytest.raises(LedgerMissingError):
        read(str(LEDGER.parent / "nope.csv"))
