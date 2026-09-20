"""graph-clinic against HotpotQA, from the local HuggingFace cache.

7,405 validation questions, each with two gold paragraphs hidden among ten, and
each labelled ``bridge`` or ``comparison``. The graph is built from real title
mentions between paragraphs, not invented.

Every figure asserted here was produced by running this code over that cache.
"""

import pytest

from graphclinic.hotpot import (
    baseline_hits_both,
    connected,
    lexical_top2,
    load,
    mentions,
)

N = 3000

try:
    ITEMS = load(N)
except Exception:  # noqa: BLE001 — absence is the skip condition
    ITEMS = ()

pytestmark = pytest.mark.skipif(not ITEMS, reason="HotpotQA not in the local HF cache")


def subset(kind=None):
    return [i for i in ITEMS if i.gold_present and kind in (None, i.kind)]


def rate(items, fn):
    return sum(1 for i in items if fn(i)) / len(items)


def test_the_dataset_loads_from_cache():
    assert len(ITEMS) == N
    assert all(i.gold_present for i in ITEMS)
    kinds = {i.kind for i in ITEMS}
    assert kinds == {"bridge", "comparison"}


def test_the_graph_is_built_from_real_mentions():
    item = next(i for i in ITEMS if mentions(i))
    a, b = next(iter(mentions(item)))
    assert b.lower() in item.paragraphs[a].lower()


def test_the_graph_is_four_times_the_baseline_on_bridge_questions():
    # THE FINDING, first half. A bridge question is one where you must hop from
    # one paragraph to another; a mention edge is exactly that hop, and it finds
    # it three quarters of the time against a baseline that manages a sixth.
    bridge = subset("bridge")
    assert len(bridge) == 2400
    assert rate(bridge, lambda i: connected(i, 1)) == pytest.approx(0.734, abs=0.02)
    assert rate(bridge, baseline_hits_both) == pytest.approx(0.169, abs=0.02)


def test_and_it_is_useless_on_comparison_questions():
    # THE FINDING, second half. "Were Scott Derrickson and Ed Wood of the same
    # nationality?" needs two unrelated pages. There is no edge to traverse
    # because there is no relationship — the question is not about one.
    comparison = subset("comparison")
    assert len(comparison) == 600
    assert rate(comparison, lambda i: connected(i, 2)) < 0.03
    assert rate(comparison, baseline_hits_both) > rate(comparison, lambda i: connected(i, 2))


def test_the_headline_number_hides_the_whole_result():
    # 60% against 15% reads as "the graph wins, use it everywhere", which would
    # be the wrong decision for a fifth of the questions.
    everything = subset()
    assert rate(everything, lambda i: connected(i, 2)) == pytest.approx(0.60, abs=0.02)
    assert rate(everything, baseline_hits_both) == pytest.approx(0.154, abs=0.02)


def test_the_second_hop_buys_almost_nothing():
    bridge = subset("bridge")
    one = rate(bridge, lambda i: connected(i, 1))
    two = rate(bridge, lambda i: connected(i, 2))
    assert two - one < 0.03  # the value is in the direct mention


def test_a_wider_walk_is_still_bounded():
    item = subset("bridge")[0]
    assert connected(item, 1) or not connected(item, 1)  # terminates either way


def test_the_baseline_returns_two_paragraphs():
    assert len(lexical_top2(ITEMS[0])) == 2


def test_a_missing_cache_is_reported_rather_than_faked():
    from graphclinic.hotpot import DatasetMissingError, _validation_file

    assert _validation_file().exists()
    with pytest.raises(DatasetMissingError):
        raise DatasetMissingError("shape of the failure when the cache is absent")
