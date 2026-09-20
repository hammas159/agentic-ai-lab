import pytest

from hiredesk.domain import Rubric, blind_view, leaks, score_delta, total


def cv():
    return {
        "name": "Ayesha Khan",
        "email": "ayesha.khan@example.com",
        "phone": "+92 300 1234567",
        "gender": "female",
        "summary": "Ayesha Khan is a backend engineer with eight years on payments.",
        "experience": "Reach me at ayesha.khan@example.com or +92 300 1234567.",
        "skills": ["python", "postgres"],
    }


def test_identifying_keys_are_removed():
    blind = blind_view(cv())
    assert "name" not in blind.view
    assert set(blind.removed) >= {"name", "email", "phone", "gender"}


def test_the_name_does_not_survive_in_the_free_text():
    # The failure that quietly defeats blind scoring.
    blind = blind_view(cv())
    assert "Ayesha" not in blind.view["summary"]
    assert "Khan" not in blind.view["summary"]


def test_an_email_in_free_text_is_scrubbed():
    blind = blind_view(cv())
    assert "@example.com" not in blind.view["experience"]


def test_a_phone_number_in_free_text_is_scrubbed():
    blind = blind_view(cv())
    assert "1234567" not in blind.view["experience"]


def test_non_identifying_fields_are_untouched():
    assert blind_view(cv()).view["skills"] == ["python", "postgres"]


def test_the_leak_check_passes_on_a_clean_view():
    assert leaks(blind_view(cv()), ["Ayesha", "Khan"]) == []


def test_the_leak_check_catches_what_redaction_missed():
    leaky = blind_view({"skills": ["python"], "notes": "referred by Ayesha"})
    assert leaks(leaky, ["Ayesha"]) == ["Ayesha"]


def test_total_is_summed_in_python():
    rubric = Rubric(("depth", "breadth", "communication"))
    assert total(rubric, {"depth": 4, "breadth": 3, "communication": 5}) == 12


def test_an_unscored_dimension_is_refused():
    with pytest.raises(ValueError):
        total(Rubric(("depth", "breadth")), {"depth": 4})


def test_a_dimension_outside_the_rubric_is_refused():
    with pytest.raises(ValueError):
        total(Rubric(("depth",)), {"depth": 4, "vibe": 5})


def test_a_score_outside_the_range_is_refused():
    with pytest.raises(ValueError):
        total(Rubric(("depth",)), {"depth": 9})


def test_score_delta_is_what_the_name_was_worth():
    assert score_delta(14, 11) == 3
