"""one-desk's adaptation claim, against a human baseline.

`products/data/ami_manual.zip` carries up to four participant summaries per AMI
meeting — the same meeting, written up independently by each person who was in
it. Same content, four renderings, nobody instructed to differ.

That is the yardstick a per-platform adapter should be held to. Every figure
asserted here was produced by running this code over that file.
"""

import pytest

from onedesk.domain import overlap as variant_overlap
from onedesk.variants import ARCHIVE, baseline, by_meeting, overlap, renderings

pytestmark = pytest.mark.skipif(not ARCHIVE.exists(), reason="AMI corpus not on disk")

BASE = "One 14B on one 16 GB card serves every agent in the system. Here is what that forces."
REWRITE = (
    "One 14B on one 16 GB card serves every agent we run. "
    "Here is what that forces you to build."
)


@pytest.fixture(scope="module")
def measured():
    return baseline()


def test_the_summaries_load():
    assert len(renderings()) == 300
    assert len(by_meeting()) == 80


def test_two_people_describing_one_meeting_share_about_a_quarter(measured):
    # THE BASELINE. Four people were in the same room, describing the same
    # hour, with no instruction to vary their wording. Median overlap: 0.23.
    assert measured.same_pairs == 397
    assert measured.same_median == pytest.approx(0.229, abs=0.02)


def test_and_two_people_describing_different_meetings_share_nearly_as_much(measured):
    # The control. Independent renderings of the SAME content are barely more
    # alike than renderings of different content — which is what genuine
    # variation looks like.
    assert measured.different_median == pytest.approx(0.159, abs=0.02)
    assert measured.separation < 0.10


def test_a_hand_written_pair_is_not_a_measurement(measured):
    # This pair was what the finding originally rested on, and it overstated
    # the case: a real adapter run gives 0.53, not 0.79. Kept as a unit test of
    # `overlap`, and no longer as evidence about adapters. The real measurement
    # is in test_real_adapter.py.
    assert variant_overlap(REWRITE, BASE) == pytest.approx(0.786, abs=0.02)


def test_overlap_is_containment_not_jaccard():
    # A shorter text must not score well merely for being shorter.
    short = renderings()[0]
    assert overlap(short, short) == 1.0


def test_a_rendering_needs_enough_words_to_measure():
    # Summaries under thirty words are excluded: two sentences share or do not
    # share a handful of words and the ratio is noise.
    assert all(len(r.text.split()) >= 30 for r in renderings())


def test_every_rendering_knows_who_wrote_it():
    sample = renderings()[0]
    assert sample.author.isalpha()
    assert sample.meeting


def test_a_missing_corpus_is_reported_rather_than_faked():
    from onedesk.variants import CorpusMissingError

    with pytest.raises(CorpusMissingError):
        renderings(str(ARCHIVE.parent / "nope.zip"))
