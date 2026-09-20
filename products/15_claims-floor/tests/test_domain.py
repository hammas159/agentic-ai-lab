from datetime import date

import pytest

from claimsfloor.domain import (
    EXCLUDED,
    NOT_A_LISTED_PERIL,
    NoVersionInForceError,
    OverlappingVersionsError,
    PolicyVersion,
    assess,
    version_for,
    wrong_version_rate,
)


def versions():
    return [
        PolicyVersion(
            "v1",
            date(2024, 1, 1),
            date(2025, 12, 31),
            perils=frozenset({"fire", "flood", "theft"}),
        ),
        PolicyVersion(
            "v2",
            date(2026, 1, 1),
            None,
            perils=frozenset({"fire", "theft"}),
            exclusions=frozenset({"flood"}),
        ),
    ]


def test_the_wording_in_force_is_chosen_by_the_loss_date():
    assert version_for(versions(), date(2025, 6, 1)).id == "v1"
    assert version_for(versions(), date(2026, 6, 1)).id == "v2"


def test_the_boundary_days_belong_to_the_right_version():
    assert version_for(versions(), date(2025, 12, 31)).id == "v1"
    assert version_for(versions(), date(2026, 1, 1)).id == "v2"


def test_a_loss_before_any_wording_is_refused_not_defaulted():
    with pytest.raises(NoVersionInForceError):
        version_for(versions(), date(2023, 5, 1))


def test_a_gap_between_versions_is_refused():
    gapped = [
        PolicyVersion("v1", date(2024, 1, 1), date(2024, 12, 31), frozenset({"fire"})),
        PolicyVersion("v2", date(2026, 1, 1), None, frozenset({"fire"})),
    ]
    with pytest.raises(NoVersionInForceError):
        version_for(gapped, date(2025, 6, 1))


def test_overlapping_versions_are_surfaced_not_silently_resolved():
    overlapping = [
        PolicyVersion("v1", date(2024, 1, 1), date(2026, 6, 30), frozenset({"fire"})),
        PolicyVersion("v2", date(2026, 1, 1), None, frozenset({"fire"})),
    ]
    with pytest.raises(OverlappingVersionsError):
        version_for(overlapping, date(2026, 3, 1))


def test_a_version_ending_before_it_starts_is_refused():
    with pytest.raises(ValueError):
        PolicyVersion("v", date(2026, 5, 1), date(2026, 1, 1), frozenset())


def test_the_same_peril_is_covered_under_one_version_and_excluded_under_the_next():
    # This is the finding, as a test: flood on the same policy, two loss dates.
    assert assess(versions(), date(2025, 6, 1), "flood").covered
    later = assess(versions(), date(2026, 6, 1), "flood")
    assert not later.covered
    assert later.reason == EXCLUDED


def test_coverage_always_names_the_version_it_was_decided_under():
    assert assess(versions(), date(2025, 6, 1), "fire").version_id == "v1"


def test_an_unlisted_peril_is_not_covered():
    assert assess(versions(), date(2026, 6, 1), "earthquake").reason == NOT_A_LISTED_PERIL


def test_the_wrong_version_rate_is_the_measurement():
    assert wrong_version_rate(["v2", "v1", "v2"], ["v1", "v1", "v2"]) == pytest.approx(1 / 3)


def test_the_two_lists_must_line_up():
    with pytest.raises(ValueError):
        wrong_version_rate(["v1"], [])
