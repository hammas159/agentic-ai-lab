import pytest

from agridesk.domain import (
    Isolate,
    collapse_clonal,
    distinct_variants,
    emerging,
    false_alarm_rate,
)


def repeated():
    """One isolate, sequenced nine times at one site. The real-world case."""
    return [Isolate(f"i{n}", "ACGTACGT", "multan", day=10 + n) for n in range(9)]


def test_nine_sequencings_of_one_isolate_are_one_observation():
    clusters = collapse_clonal(repeated())
    assert len(clusters) == 1
    assert clusters[0].size == 9
    assert clusters[0].clonal


def test_the_uncollapsed_count_is_what_produces_the_false_alarm():
    assert distinct_variants(repeated(), collapse=False) == 9
    assert distinct_variants(repeated(), collapse=True) == 1


def test_the_same_sequence_at_two_sites_stays_two_observations():
    isolates = [
        Isolate("i1", "ACGT", "multan", 10),
        Isolate("i2", "ACGT", "sahiwal", 11),
    ]
    assert len(collapse_clonal(isolates)) == 2


def test_a_cluster_remembers_when_it_was_first_seen():
    clusters = collapse_clonal(repeated())
    assert clusters[0].first_seen == 10


def test_an_isolate_without_a_sequence_is_refused():
    with pytest.raises(ValueError):
        Isolate("i1", "", "multan", 10)


def test_one_site_repeating_itself_is_not_emergence():
    assert emerging(repeated(), since_day=5) == []


def test_a_sequence_at_two_sites_is_emergence():
    isolates = [
        Isolate("i1", "TTTT", "multan", 20),
        Isolate("i2", "TTTT", "sahiwal", 21),
    ]
    assert emerging(isolates, since_day=15) == ["TTTT"]


def test_something_already_present_before_the_window_is_not_emerging():
    isolates = [
        Isolate("i1", "TTTT", "multan", 1),
        Isolate("i2", "TTTT", "sahiwal", 21),
    ]
    assert emerging(isolates, since_day=15) == []


def test_the_site_threshold_is_configurable():
    isolates = [Isolate("i1", "TTTT", "multan", 20)]
    assert emerging(isolates, since_day=15, min_sites=1) == ["TTTT"]


def test_an_impossible_site_threshold_is_refused():
    with pytest.raises(ValueError):
        emerging([], since_day=1, min_sites=0)


def test_the_false_alarm_rate_is_the_headline():
    # One sequence, nine sequencings, one site: every naive call is spurious.
    assert false_alarm_rate(repeated(), since_day=5) == 1.0


def test_no_recent_isolates_means_no_alarms_rather_than_a_crash():
    assert false_alarm_rate(repeated(), since_day=999) == 0.0
