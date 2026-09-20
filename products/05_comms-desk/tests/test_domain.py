import pytest

from comms.domain import Commitment, cross_source, dedupe, duplicate_rate, similarity

MEETING = "I will send the revised pricing sheet to the client before Friday"
EMAIL = "Sending the revised pricing sheet over to the client by Friday"


def test_the_same_promise_in_two_wordings_is_one_commitment():
    items = [
        Commitment("c1", "ayesha", MEETING, "meeting"),
        Commitment("c2", "ayesha", EMAIL, "email"),
    ]
    clusters = dedupe(items, threshold=0.4)
    assert len(clusters) == 1
    assert clusters[0].is_duplicate


def test_two_speakers_making_similar_promises_are_never_merged():
    items = [
        Commitment("c1", "ayesha", MEETING, "meeting"),
        Commitment("c2", "bilal", MEETING, "email"),
    ]
    assert len(dedupe(items, threshold=0.1)) == 2


def test_short_commitments_do_not_match_each_other_trivially():
    assert similarity("send it", "send it") == 0.0


def test_unrelated_commitments_stay_apart():
    items = [
        Commitment("c1", "ayesha", MEETING, "meeting"),
        Commitment("c2", "ayesha", "I will book the venue for the October offsite", "email"),
    ]
    assert len(dedupe(items)) == 2


def test_duplicate_rate_is_reported():
    items = [
        Commitment("c1", "ayesha", MEETING, "meeting"),
        Commitment("c2", "ayesha", EMAIL, "email"),
        Commitment("c3", "ayesha", "I will book the venue for the October offsite", "email"),
    ]
    assert duplicate_rate(items, threshold=0.4) == pytest.approx(1 / 3)


def test_an_empty_list_has_no_rate_rather_than_dividing_by_zero():
    assert duplicate_rate([]) == 0.0


def test_a_commitment_confirmed_by_both_sources_is_findable():
    items = [
        Commitment("c1", "ayesha", MEETING, "meeting"),
        Commitment("c2", "ayesha", EMAIL, "email"),
    ]
    both = cross_source(dedupe(items, threshold=0.4))
    assert len(both) == 1
    assert both[0].sources == {"meeting", "email"}


def test_an_impossible_threshold_is_refused():
    with pytest.raises(ValueError):
        dedupe([], threshold=0.0)
