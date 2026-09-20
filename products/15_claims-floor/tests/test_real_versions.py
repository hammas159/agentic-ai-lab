"""claims-floor against real versioned regulation.

`products/data/ecfr_title29.json` is the eCFR version index for Title 29
(Labor): 1,000 real section versions with the date each amendment took effect.

Regulation stands in for insurance policy wordings because insurers do not
publish a machine-readable archive of superseded wordings. The structure is the
same — a document with a history, and a question about a date — and it is real,
which an invented archive would not be.

Every figure asserted here was produced by running this code over that file.
"""

import statistics
from datetime import date

import pytest

from claimsfloor.ecfr import (
    INDEX,
    amended,
    history,
    in_force,
    latest,
    versions,
    wrong_version_rate,
)

pytestmark = pytest.mark.skipif(not INDEX.exists(), reason="eCFR index not on disk")


def test_the_index_loads():
    assert len(versions()) == 1000
    assert len(history()) == 577


def test_half_the_sections_have_been_amended():
    assert len(amended()) == 272
    sizes = [len(v) for v in amended().values()]
    assert statistics.median(sizes) == 2
    assert max(sizes) == 11  # one section amended eleven times


def test_the_index_contains_same_day_duplicates():
    # Several sections carry two entries with the same amendment date. Picking
    # a test case without checking for that produced a spurious failure, so it
    # is recorded here rather than worked around silently.
    same_day = [
        s for s, rows in amended().items()
        if len({r.effective for r in rows}) < len(rows)
    ]
    assert same_day


def test_in_force_picks_the_version_that_was_current_on_the_date():
    section, rows = next(
        (s, r) for s, r in sorted(amended().items())
        if r[0].effective < r[1].effective
    )
    first, second = rows[0], rows[1]
    # The day before the second amendment, the first is still in force.
    day_before = date.fromordinal(second.effective.toordinal() - 1)
    assert in_force(section, day_before).effective == first.effective
    assert in_force(section, second.effective).effective == second.effective


def test_a_date_before_any_version_has_no_answer():
    section, rows = next(iter(sorted(amended().items())))
    assert in_force(section, date(1900, 1, 1)) is None


def test_returning_the_current_text_is_wrong_half_the_time():
    # THE FINDING. For a section that has ever been amended, answering from the
    # current text answers a different question than the one asked, in 52% of
    # the cases where the date matters.
    rate, mismatches = wrong_version_rate()
    assert rate == pytest.approx(0.522, abs=0.02)
    assert len(mismatches) == 363


def test_and_it_can_be_a_decade_out():
    _, mismatches = wrong_version_rate()
    gaps = [m.years_out for m in mismatches]
    assert max(gaps) == pytest.approx(9.6, abs=0.3)
    # The median is small because most amendments are recent. The tail is what
    # decides a claim wrongly.
    assert statistics.median(gaps) < 1.0


def test_the_latest_version_is_not_the_answer_to_a_dated_question():
    section = next(
        s for s, rows in sorted(amended().items())
        if rows[0].effective != rows[-1].effective
    )
    rows = history()[section]
    assert in_force(section, rows[0].effective).effective == rows[0].effective
    assert latest(section).effective == rows[-1].effective
    assert in_force(section, rows[0].effective) != latest(section)


def test_an_unknown_section_returns_nothing_rather_than_guessing():
    assert in_force("not-a-section", date(2020, 1, 1)) is None
    assert latest("not-a-section") is None


def test_a_missing_index_is_reported_rather_than_faked():
    from claimsfloor.ecfr import IndexMissingError

    with pytest.raises(IndexMissingError):
        versions(str(INDEX.parent / "nope.json"))
