"""ward-sync against real Synthea patient records.

`products/data/synthea_csv.zip` is Synthea's published sample — openly
available, no credentialing. Medications carry a START and a STOP, so a drug
that was discontinued is visible as an event rather than as an absence.

Every figure asserted here was produced by running this code over that file.
"""

import statistics

import pytest

from ward.domain import Event, Sentence, active_medications, cite_or_drop, discontinued
from ward.synthea import ARCHIVE, discrepancies, encounters, medications

pytestmark = pytest.mark.skipif(not ARCHIVE.exists(), reason="Synthea sample not on disk")


@pytest.fixture(scope="module")
def meds():
    return medications()


@pytest.fixture(scope="module")
def gaps():
    return discrepancies()


def test_the_records_load(meds):
    assert len(meds) == 3_850
    assert len(encounters()) == 5_571
    assert len({m.patient for m in meds}) == 105


def test_almost_every_prescription_is_eventually_stopped(meds):
    stopped = [m for m in meds if m.stopped]
    assert len(stopped) / len(meds) == pytest.approx(0.930, abs=0.01)


def test_a_quarter_of_them_are_a_single_administration(meds):
    same_day = [m for m in meds if m.same_day]
    assert len(same_day) == 1_006
    assert 0.2 < len(same_day) / len(meds) < 0.3


def test_the_naive_list_names_a_stopped_drug_for_almost_every_patient(gaps):
    # THE FINDING. A "current medication list" assembled by asking what was
    # started, and never what was stopped, is wrong for 104 of 105 patients.
    affected = [g for g in gaps if g.would_name_a_stopped_drug]
    assert len(affected) == 104
    assert len(affected) / len(gaps) > 0.98


def test_the_naive_list_is_five_times_too_long(gaps):
    affected = [g for g in gaps if g.would_name_a_stopped_drug]
    median = statistics.median(g.overstatement for g in affected)
    assert median == pytest.approx(5.54, abs=0.2)


def test_reading_the_event_stream_is_the_fix():
    # The same question on an encounter's events, which is what this product
    # actually does: ordered, ceftriaxone stopped, co-amoxiclav still in force.
    stream = [
        Event("evt_1", 1, "ordered", "ceftriaxone"),
        Event("evt_2", 2, "discontinued", "ceftriaxone"),
        Event("evt_3", 3, "ordered", "co-amoxiclav"),
    ]
    assert [a.drug for a in active_medications(stream)] == ["co-amoxiclav"]
    assert discontinued(stream) == {"ceftriaxone"}


def test_a_real_patient_rebuilds_correctly(meds):
    # Take the busiest real patient and rebuild their medication state from
    # START/STOP events rather than from the list of everything started.
    from collections import Counter

    busiest = Counter(m.patient for m in meds).most_common(1)[0][0]
    theirs = [m for m in meds if m.patient == busiest]
    events, seq = [], 0
    for med in sorted(theirs, key=lambda m: m.start):
        seq += 1
        events.append(Event(f"start_{seq}", seq, "ordered", med.description))
        if med.stopped:
            seq += 1
            events.append(Event(f"stop_{seq}", seq, "discontinued", med.description))

    active = {a.drug for a in active_medications(events)}
    naive = {m.description for m in theirs}
    assert active < naive  # strictly fewer
    assert naive - active  # and the difference is non-empty


def test_a_summary_naming_a_stopped_drug_is_dropped_before_review():
    stream = [
        Event("evt_1", 1, "ordered", "ceftriaxone"),
        Event("evt_2", 2, "discontinued", "ceftriaxone"),
    ]
    draft = cite_or_drop(
        [
            Sentence("Ceftriaxone was stopped after a documented rash.", ("evt_2",)),
            Sentence("The patient continues on ceftriaxone."),
        ],
        stream,
    )
    assert len(draft.kept) == 1
    assert draft.dropped[0].text.endswith("continues on ceftriaxone.")


def test_missing_records_are_reported_rather_than_faked():
    from ward.synthea import RecordsMissingError

    with pytest.raises(RecordsMissingError):
        medications(str(ARCHIVE.parent / "nope.zip"))
