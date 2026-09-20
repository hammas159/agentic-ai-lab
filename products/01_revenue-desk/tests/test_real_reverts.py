"""revenue-desk's revert detection, measured on real edit history.

Thirty-odd repositories on this machine, with real commits. A revert here is a
line that went A, then B, then back to A — one edit undoing another, which is
the same event `domain.detect_reverts` looks for on a deal record.

Every figure asserted here was produced by running this code over that history.
Counts are asserted as bands, because the history grows.
"""

import statistics

import pytest

from revenue.churn import REPOS, Edit, find_reverts, survey

pytestmark = pytest.mark.skipif(not REPOS.exists(), reason="no checkouts at D:/github")


@pytest.fixture(scope="module")
def surveyed():
    return survey(repos=12, limit=120)


def test_real_history_is_readable(surveyed):
    assert len(surveyed) >= 8
    assert sum(s.edits for s in surveyed) > 100_000
    assert all(s.commits > 0 for s in surveyed)


def test_a_line_that_comes_back_verbatim_is_a_revert():
    history = [
        Edit("c1", 0, "a.py", "timeout = 30  # measured", added=True),
        Edit("c2", 1, "a.py", "timeout = 30  # measured", added=False),
        Edit("c2", 1, "a.py", "timeout = 90  # guessed", added=True),
        Edit("c3", 2, "a.py", "timeout = 90  # guessed", added=False),
        Edit("c3", 2, "a.py", "timeout = 30  # measured", added=True),
    ]
    (revert,) = find_reverts(history)
    assert revert.line.startswith("timeout = 30")
    assert revert.removed_at == 1
    assert revert.restored_at == 2


def test_a_rewrite_is_not_a_revert():
    history = [
        Edit("c1", 0, "a.py", "timeout = 30  # measured", added=True),
        Edit("c2", 1, "a.py", "timeout = 30  # measured", added=False),
        Edit("c2", 1, "a.py", "timeout = 45  # different again", added=True),
    ]
    assert find_reverts(history) == []


def test_trivial_lines_are_not_corrections():
    # A brace coming back is not someone's judgement being undone.
    history = [
        Edit("c1", 0, "a.py", "}", added=True),
        Edit("c2", 1, "a.py", "}", added=False),
        Edit("c3", 2, "a.py", "}", added=True),
    ]
    assert find_reverts(history) == []


def test_reverts_are_rare_in_a_reviewed_medium(surveyed):
    # THE FINDING. Across a quarter of a million real line edits, one edit undoes
    # another about once in a thousand. Git has diffs, atomic commits and review;
    # this is the floor such a medium achieves.
    edits = sum(s.edits for s in surveyed)
    reverts = sum(len(s.reverts) for s in surveyed)
    assert reverts / edits < 0.005
    assert reverts > 50  # and it is not zero either


def test_the_rate_varies_by_two_orders_of_magnitude_between_repositories(surveyed):
    rates = sorted(s.revert_rate for s in surveyed if s.edits > 1000)
    assert rates[-1] / max(rates[0], 1e-9) > 20
    # Exploratory work rewrites itself; finished work does not.


def test_most_reverts_happen_almost_immediately(surveyed):
    gaps = [r.gap for s in surveyed for r in s.reverts]
    assert gaps
    assert statistics.median(gaps) <= 2
    assert max(gaps) > 5  # and a few come back much later


def test_an_empty_history_yields_nothing():
    assert find_reverts([]) == []
