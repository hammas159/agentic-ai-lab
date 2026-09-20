"""comms-desk against the real AMI Meeting Corpus.

`products/data/ami_manual.zip` is AMI's manual annotation set: real recorded
meetings, hand-annotated with dialogue acts and — the part that matters — with
the speaker. A commitment nobody made is not a commitment, and AMI is one of the
few corpora where that attribution is ground truth rather than a diarisation
guess.

Every figure asserted here was produced by running this code over that file.
"""

import pytest

from comms.ami import ARCHIVE, COMMITMENT_ACTS, commitments, utterances
from comms.domain import Commitment, dedupe

pytestmark = pytest.mark.skipif(not ARCHIVE.exists(), reason="AMI corpus not on disk")

MEETINGS = 12


@pytest.fixture(scope="module")
def acts():
    return utterances(limit_meetings=MEETINGS)


@pytest.fixture(scope="module")
def items():
    found = commitments(limit_meetings=MEETINGS)
    return [Commitment(f"c{i}", u.key, u.text, "meeting") for i, u in enumerate(found)]


def merges(items, threshold, speaker_blind=False):
    subject = (
        [Commitment(c.id, "ANY", c.text, c.source) for c in items]
        if speaker_blind
        else items
    )
    return len(subject) - len(dedupe(subject, threshold=threshold))


def test_the_corpus_parses_with_speakers(acts):
    assert len(acts) == 9_550
    assert len({a.meeting for a in acts}) == MEETINGS
    assert len({a.key for a in acts}) == 48  # speaker slots, not just speakers
    assert all(a.speaker.isalpha() for a in acts)


def test_only_suggest_and_offer_count_as_commitments(acts, items):
    assert {"sug", "off"} == COMMITMENT_ACTS
    assert len(items) == 922
    # Backchannels and stalls are the bulk of a real meeting and commit nobody.
    chatter = [a for a in acts if a.act in {"bck", "stl", "fra"}]
    assert len(chatter) > len(items) * 2


def test_people_rarely_restate_a_commitment_inside_one_meeting(items):
    # 1% at a threshold loose enough to catch real restatements. Within a single
    # meeting, saying the same thing twice is uncommon — which is why the
    # duplication this product targets is a CROSS-SOURCE problem.
    assert merges(items, 0.5) == 10
    assert merges(items, 0.5) / len(items) < 0.02


def test_dropping_the_speaker_barrier_merges_two_different_people(items):
    # THE FINDING. At the threshold you need for genuine restatements, ignoring
    # who spoke produces 26 merges of which 16 join two different speakers.
    # Sixty-two per cent of everything it merges is wrong.
    with_speaker = merges(items, 0.5)
    speaker_blind = merges(items, 0.5, speaker_blind=True)
    assert with_speaker == 10
    assert speaker_blind == 26
    wrong = speaker_blind - with_speaker
    assert wrong == 16
    assert wrong / speaker_blind > 0.6


def test_the_damage_is_worst_exactly_where_the_threshold_is_useful(items):
    # Tighten the threshold and the wrong merges vanish - along with the right
    # ones. At 0.7 nothing cross-speaker merges and nothing else does either.
    blind = merges(items, 0.7, speaker_blind=True)
    assert blind - merges(items, 0.7) == 0
    assert merges(items, 0.7) == 3


def test_speaker_is_a_barrier_not_a_weighted_feature():
    # No threshold, however loose, merges across speakers.
    pair = [
        Commitment(
            "c1", "ayesha", "I will send the revised pricing sheet on Friday", "meeting"
        ),
        Commitment(
            "c2", "bilal", "I will send the revised pricing sheet on Friday", "meeting"
        ),
    ]
    assert len(dedupe(pair, threshold=0.01)) == 2


def test_a_real_utterance_survives_the_round_trip(items):
    first = items[0]
    assert first.speaker.count(":") == 1  # meeting:speaker
    assert first.text.strip()


def test_a_missing_corpus_is_reported_rather_than_faked():
    from comms.ami import CorpusMissingError

    with pytest.raises(CorpusMissingError):
        utterances(str(ARCHIVE.parent / "nope.zip"))
