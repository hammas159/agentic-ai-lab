import pytest

from kycfloor.domain import alias_recall, normalise, same_person, screen


def test_transliterations_of_one_name_normalise_together():
    assert normalise("Mohammad Hassan") == normalise("Muhammad Hasan")


def test_diacritics_do_not_create_a_second_person():
    assert same_person("Ayesha Khán", "Ayesha Khan")


def test_token_order_does_not_matter():
    assert same_person("Khan Ayesha", "Ayesha Khan")


def test_particles_attached_or_detached_are_the_same_name():
    assert same_person("al-Hassan Ahmed", "Alhassan Ahmed")


def test_a_known_limitation_suffix_particles_do_not_merge():
    # "Abd-ul Rahman" splits to abd + rahman; "Abdul Rahman" keeps abdul.
    # Leading particles are handled, trailing ones are not. Stated rather than
    # hidden, because a screening tool that quietly misses is worse than one
    # whose gap is written down.
    assert not same_person("Abd-ul Rahman Khan", "Abdul Rahman Khan")


def test_two_different_people_do_not_match():
    assert not same_person("Ayesha Khan", "Bilal Ahmed")


def test_a_single_token_name_does_not_match_everyone():
    # Without the floor, "Ahmed" is a subset of every name containing it.
    assert not same_person("Ahmed", "Ahmed Bilal Khan")


def test_a_longer_listed_name_still_matches_a_shorter_record():
    assert same_person("Ayesha Khan", "Ayesha Bibi Khan")


def test_screening_returns_every_candidate_not_the_best_one():
    listed = ["Muhammad Hasan", "Mohammed Hassan", "Bilal Ahmed"]
    hits = screen("Mohammad Hassan", listed)
    assert {h.listed for h in hits} == {"Muhammad Hasan", "Mohammed Hassan"}


def test_screening_a_clean_name_returns_nothing():
    assert screen("Zainab Sheikh", ["Bilal Ahmed"]) == []


def test_alias_recall_is_reported():
    assert alias_recall({"a", "b"}, {"a", "b", "c"}) == pytest.approx(2 / 3)


def test_recall_is_undefined_without_true_aliases():
    with pytest.raises(ValueError):
        alias_recall(set(), set())
