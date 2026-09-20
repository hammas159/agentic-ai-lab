from datetime import date

import pytest

from biddesk.domain import Requirement, days_to_deadline, evaluate, mandatory_recall, urgency


def reqs():
    return [
        Requirement("r1", "PEC registration valid at submission", True, "clause 4.2 p7"),
        Requirement("r2", "Audited accounts, three years", True, "clause 4.5 p8"),
        Requirement("r3", "Bid security, 2% of quoted value", True, "clause 6.1 p12"),
        Requirement("r4", "Preferred: ISO 27001", False, "clause 9.1 p18"),
    ]


def test_a_complete_bid_is_submittable():
    out = evaluate(reqs(), {"r1", "r2", "r3", "r4"})
    assert out.submittable
    assert out.missing_mandatory == []


def test_one_missing_mandatory_item_blocks_the_whole_bid():
    out = evaluate(reqs(), {"r1", "r2", "r4"})
    assert not out.submittable
    assert out.missing_mandatory == ["r3"]


def test_a_missing_optional_item_does_not_block():
    out = evaluate(reqs(), {"r1", "r2", "r3"})
    assert out.submittable
    assert out.missing_optional == ["r4"]


def test_mandatory_recall_ignores_the_optional_items():
    # An extractor that found every optional item and two of three mandatory
    # ones scores 0.67 here and would score 0.75 on overall recall.
    assert mandatory_recall({"r1", "r2", "r4"}, reqs()) == pytest.approx(2 / 3)


def test_perfect_mandatory_recall():
    assert mandatory_recall({"r1", "r2", "r3"}, reqs()) == 1.0


def test_recall_is_undefined_without_mandatory_items():
    with pytest.raises(ValueError):
        mandatory_recall(set(), [Requirement("r9", "nice to have", False)])


def test_days_to_deadline_is_arithmetic():
    assert days_to_deadline(date(2026, 9, 20), date(2026, 9, 22)) == 2


def test_a_month_boundary_is_not_a_judgement_call():
    assert days_to_deadline(date(2026, 9, 28), date(2026, 10, 2)) == 4


def test_a_closed_tender_is_negative_not_zero():
    assert days_to_deadline(date(2026, 9, 22), date(2026, 9, 20)) == -2


def test_urgency_bands():
    today = date(2026, 9, 20)
    assert urgency(today, date(2026, 9, 19)) == "closed"
    assert urgency(today, date(2026, 9, 22)) == "urgent"
    assert urgency(today, date(2026, 9, 27)) == "soon"
    assert urgency(today, date(2026, 10, 30)) == "watching"
