"""campus-ops against a real schedule.

`products/data/synthea_csv.zip` holds 5,571 real scheduled encounters with a
start, a stop, an organisation, a provider and a patient. That is a timetable:
room, teacher, cohort, span. The mapping is exact, which is why this answers the
question a published timetable dataset would have, on data that is real.

Every figure asserted here was produced by running this code over that file.
"""

import collections

import pytest

from campusops.domain import COHORT, ROOM, TEACHER, publishable
from campusops.schedule import ARCHIVE, bookings, clashes_by_day, report, sessions

pytestmark = pytest.mark.skipif(not ARCHIVE.exists(), reason="Synthea sample not on disk")


@pytest.fixture(scope="module")
def pairs():
    """Distinct overlapping pairs, with the dimensions each trips."""
    out = collections.defaultdict(set)
    for day, found in clashes_by_day().items():
        for clash in found:
            out[(day, clash.first, clash.second)].add(clash.dimension)
    return dict(out)


def test_the_schedule_loads():
    assert len(bookings()) == 5_571
    assert len(sessions()) == len(bookings())


def test_most_days_are_clean():
    r = report()
    assert r.days == 3_440
    assert r.clashing_days == 45
    assert r.clean_days > 0.98


def test_the_three_dimensions_are_nearly_equally_represented():
    counts = report().by_dimension
    assert counts[ROOM] == 37
    assert counts[TEACHER] == 37
    assert counts[COHORT] == 36
    # A checker that looks at one dimension is looking at a third of the problem.


def test_there_are_forty_six_real_overlaps(pairs):
    assert len(pairs) == 46


def test_most_overlaps_trip_every_dimension(pairs):
    both = collections.Counter(frozenset(v) for v in pairs.values())
    assert both[frozenset({ROOM, TEACHER, COHORT})] == 27  # a duplicate booking
    assert both[frozenset({ROOM, TEACHER})] == 10  # one clinician, two patients


def test_a_room_only_checker_misses_the_impossible_ones(pairs):
    # THE FINDING. Nine overlaps trip the cohort dimension ALONE: the same
    # person booked at two different sites with two different staff at the same
    # time. That is physically impossible and completely invisible to a checker
    # looking at rooms.
    cohort_only = [v for v in pairs.values() if v == {COHORT}]
    assert len(cohort_only) == 9

    caught_by_rooms = [v for v in pairs.values() if ROOM in v]
    assert len(caught_by_rooms) == 37
    assert len(caught_by_rooms) / len(pairs) == pytest.approx(0.80, abs=0.02)


def test_a_double_booked_teacher_is_as_common_as_a_double_booked_room(pairs):
    with_teacher = [v for v in pairs.values() if TEACHER in v]
    with_room = [v for v in pairs.values() if ROOM in v]
    assert len(with_teacher) == len(with_room) == 37


def test_a_day_with_a_clash_is_not_publishable():
    day, found = next((d, c) for d, c in clashes_by_day().items() if c)
    rows = [s for s in sessions() if s.day == day]
    assert not publishable(rows)


def test_a_clean_day_is_publishable():
    clashing = {d for d, c in clashes_by_day().items() if c}
    day = next(s.day for s in sessions() if s.day not in clashing)
    assert publishable([s for s in sessions() if s.day == day])


def test_a_missing_schedule_is_reported_rather_than_faked():
    from campusops.schedule import ScheduleMissingError

    with pytest.raises(ScheduleMissingError):
        bookings(str(ARCHIVE.parent / "nope.zip"))
