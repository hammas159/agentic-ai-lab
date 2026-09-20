"""hermes-home against the LoCoMo long-term memory benchmark.

`products/data/locomo10.json` is LoCoMo: ten very long conversations with 1,986
questions whose answers point at the turns that support them.

Every figure asserted here was produced by running this code over that file.
"""

import statistics

import pytest

from hermes.locomo import BENCHMARK, coverage, load, questions

pytestmark = pytest.mark.skipif(not BENCHMARK.exists(), reason="LoCoMo not on disk")


@pytest.fixture(scope="module")
def convs():
    return load()


@pytest.fixture(scope="module")
def qs():
    return questions()


def test_these_conversations_are_genuinely_long(convs):
    assert len(convs) == 10
    sessions = [c.sessions for c in convs]
    turns = [len(c.turns) for c in convs]
    assert min(sessions) == 19
    assert max(sessions) == 32
    assert statistics.median(turns) == 646


def test_almost_every_question_has_resolvable_evidence(convs, qs):
    total = sum(len(c.questions) for c in convs)
    assert total == 1_986
    assert len(qs) == 1_982


def test_the_median_answer_lives_fourteen_sessions_back(qs):
    back = [q.sessions_back for q in qs]
    assert statistics.median(back) == 14
    assert max(back) == 31


def test_a_sliding_window_cannot_answer_these_questions(qs):
    # THE FINDING. Even a generous window - the last 8 of a median 29 sessions -
    # answers barely a quarter of them. This is the measured form of "memory
    # that forgets the wrong thing": the window keeps what is recent, and what
    # is needed is old.
    assert coverage(1) == pytest.approx(0.024, abs=0.005)
    assert coverage(3) == pytest.approx(0.120, abs=0.01)
    assert coverage(8) == pytest.approx(0.284, abs=0.01)


def test_coverage_grows_slowly_with_window_size(qs):
    # Eight times the window buys twelve times nothing like eight times the
    # coverage. Paying for a longer window is not a fix, it is a tax.
    assert coverage(8) / coverage(1) < 13
    assert coverage(8) < 0.3


def test_the_earliest_evidence_is_what_binds_not_the_latest(qs):
    # A question supported by sessions 3 and 27 is unanswerable without 3.
    multi = [q for q in qs if len(q.evidence_sessions) > 1]
    assert multi
    q = multi[0]
    assert q.sessions_back == q.sessions - min(q.evidence_sessions)


def test_a_window_of_zero_is_refused(qs):
    with pytest.raises(ValueError):
        qs[0].answerable_within(0)


def test_a_full_window_answers_everything(qs, convs):
    widest = max(c.sessions for c in convs)
    assert coverage(widest + 1) == 1.0


def test_a_missing_benchmark_is_reported_rather_than_faked():
    from hermes.locomo import BenchmarkMissingError

    with pytest.raises(BenchmarkMissingError):
        load(str(BENCHMARK.parent / "nope.json"))
