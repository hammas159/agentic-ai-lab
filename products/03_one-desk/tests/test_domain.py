import pytest

from onedesk.domain import best_hour, compare, content_tokens, hashtags, overlap

BASE = "One 14B on one 16 GB card serves every agent in the system. Here is what that forces."


def test_content_tokens_drop_stopwords_tags_and_urls():
    got = content_tokens("The model is fast #AIengineering https://example.com")
    assert got == ["model", "fast"]


def test_hashtags_are_reported_separately():
    assert hashtags("ship it #MLOps #AIengineering") == ["#aiengineering", "#mlops"]


def test_a_reworded_variant_is_still_mostly_derivative():
    # Three new content words out of fourteen. This is what "per-platform
    # adaptation" looks like when it is measured rather than asserted.
    variant = (
        "One 14B on one 16 GB card serves every agent we run. "
        "Here is what that forces you to build."
    )
    assert overlap(variant, BASE) == pytest.approx(11 / 14)


def test_a_genuinely_different_variant_scores_low():
    assert overlap("Cotton leaf curl virus surveillance notes", BASE) < 0.2


def test_an_empty_variant_is_wholly_derivative_rather_than_a_crash():
    assert overlap("", BASE) == 0.0


def test_hashtags_do_not_inflate_apparent_difference():
    plain = "One model one card every agent"
    tagged = plain + " #AIengineering #MLOps"
    assert overlap(tagged, plain) == overlap(plain, plain)


def test_compare_orders_most_derivative_first():
    rows = compare(BASE, {"x": BASE, "ig": "Completely unrelated cotton disease text"})
    assert rows[0].platform == "x"
    assert rows[0].overlap == 1.0
    assert rows[0].added_words == 0


def test_best_hour_comes_from_history_not_from_a_model():
    assert best_hour([(9, 100), (9, 120), (20, 40)]) == 9


def test_a_tie_resolves_to_the_earlier_hour_so_the_answer_is_stable():
    assert best_hour([(9, 50), (20, 50)]) == 9


def test_no_history_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        best_hour([])


def test_an_impossible_hour_is_refused():
    with pytest.raises(ValueError):
        best_hour([(25, 10)])
