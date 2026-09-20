"""fleet-desk against a routing instance with a proven optimal answer.

`products/data/berlin52.tsp` is TSPLIB's berlin52 — 52 real locations in Berlin,
the standard benchmark — and `berlin52.opt.tour` is its proven optimal tour.

That pairing is what turns "do not let a model plan a route" from an assertion
into a number. Every figure asserted here was produced by running this code over
those files.
"""

import statistics

import pytest

from fleetdesk.domain import Comparison, cost
from fleetdesk.tsplib import (
    INSTANCE,
    OPTIMAL,
    by_index,
    cities,
    euc_2d,
    excess,
    matrix,
    nearest_neighbour,
    optimal_tour,
    sweep,
    tour_length,
)

pytestmark = pytest.mark.skipif(
    not (INSTANCE.exists() and OPTIMAL.exists()), reason="TSPLIB files not on disk"
)


def test_the_instance_loads():
    assert len(cities()) == 52
    assert len(optimal_tour()) == 52
    assert set(optimal_tour()) == {c.id for c in cities()}


def test_the_computed_optimum_matches_the_published_one():
    # 7542 is berlin52's published optimum. Reaching it from the coordinates
    # is what proves the EUC_2D rounding rule is implemented correctly —
    # using raw floats gives a number close enough to look right and wrong
    # enough to disagree with every published figure.
    assert tour_length(list(optimal_tour())) == 7542


def test_euc_2d_rounds_to_the_nearest_integer():
    a, b = cities()[0], cities()[1]
    assert isinstance(euc_2d(a, b), int)
    assert euc_2d(a, b) == euc_2d(b, a)


def test_visiting_stops_in_listed_order_is_three_times_the_distance():
    # What a model produces when asked to order stops it cannot measure: a plan
    # that visits everything exactly once and is not a route.
    assert tour_length(by_index()) == 22_205
    assert excess(by_index()) == pytest.approx(1.944, abs=0.01)


def test_the_most_plausible_reasoning_a_model_can_do_is_ninety_per_cent_worse():
    # THE FINDING. "Go round the city in a circle" is a genuinely sensible idea,
    # it is the kind of thing a model can actually reason about, and it is
    # 92% worse than optimal on real coordinates.
    assert tour_length(sweep()) == 14_497
    assert excess(sweep()) == pytest.approx(0.922, abs=0.01)


def test_even_a_proper_greedy_heuristic_is_a_fifth_worse():
    assert tour_length(nearest_neighbour()) == 8_980
    assert excess(nearest_neighbour()) == pytest.approx(0.191, abs=0.01)


def test_and_the_greedy_result_depends_on_where_it_starts():
    lengths = [tour_length(nearest_neighbour(start)) for start in range(1, 53)]
    assert min(lengths) == 8_181
    assert max(lengths) == 10_298
    assert statistics.median(lengths) == pytest.approx(9_297, abs=5)
    # A 26% spread from the starting stop alone, with the algorithm unchanged.
    assert max(lengths) / min(lengths) > 1.25


def test_the_product_costs_a_route_on_the_same_matrix():
    # The domain core, fed the real instance rather than a toy one.
    m = matrix()
    order = [str(i) for i in optimal_tour()]
    depot = order[0]
    stops = set(order[1:])
    assert cost(order + [depot], m, stops, depot) == 7542


def test_a_challenger_is_scored_against_the_solver_not_asserted_about():
    solver = tour_length(list(optimal_tour()))
    challenger = tour_length(sweep())
    result = Comparison(solver=solver, challenger=challenger)
    assert not result.challenger_won
    assert result.pct_worse == pytest.approx(0.922, abs=0.01)


def test_a_missing_instance_is_reported_rather_than_faked():
    from fleetdesk.tsplib import InstanceMissingError

    with pytest.raises(InstanceMissingError):
        cities(str(INSTANCE.parent / "nope.tsp"))
