"""revenue-desk's revert detection, measured on real edit history.

All 35 repositories on this machine, full history — 424 commits, 583,531 line
edits. A revert here is a line that went A, then B, then back to A: one edit
undoing another, which is the same event `domain.detect_reverts` looks for on a
deal record.

The headline is not the rate. It is that **the rate is 14.5x too high unless you
first decide what counts as an edit** — and that is exactly the decision this
product has to get right on a CRM where agents and people write into the same
records. Counts are asserted as bands where the history grows, and exactly where
the point is the number itself.
"""

import statistics

import pytest

from revenue.churn import REPOS, Edit, find_reverts, is_authored, survey

pytestmark = pytest.mark.skipif(not REPOS.exists(), reason="no checkouts at D:/github")


@pytest.fixture(scope="module")
def surveyed():
    return survey()  # no repo cap, full history


def totals(surveyed):
    return (
        sum(s.edits for s in surveyed),
        sum(len(s.reverts) for s in surveyed),
        sum(s.authored_edits for s in surveyed),
        sum(len(s.authored_reverts) for s in surveyed),
    )


def test_the_whole_portfolio_is_read(surveyed):
    assert len(surveyed) == 35
    assert sum(s.commits for s in surveyed) > 400
    assert sum(s.edits for s in surveyed) > 500_000
    assert all(s.commits > 0 for s in surveyed)


def test_capping_the_repositories_could_only_undercount():
    # A revert is a PAIR of edits drawn from the history pool, so shrinking the
    # pool shrinks the pairs superlinearly. The old default stopped at 12
    # repositories, alphabetically, and reported a rate far below the truth.
    twelve = survey(repos=12)
    assert len(twelve) == 12
    partial = sum(len(s.reverts) for s in twelve) / sum(s.edits for s in twelve)
    everything = survey()
    full = sum(len(s.reverts) for s in everything) / sum(s.edits for s in everything)
    assert partial < full


def test_generated_files_are_half_the_edits_and_nearly_all_the_reverts(surveyed):
    # THE FINDING. Committed datasets and regenerated `results.json` files are
    # 55% of every line edit in the portfolio — and 97% of every revert.
    edits, reverts, authored_edits, authored_reverts = totals(surveyed)
    generated_edits = (edits - authored_edits) / edits
    generated_reverts = (reverts - authored_reverts) / reverts
    assert generated_edits == pytest.approx(0.548, abs=0.05)
    assert generated_reverts == pytest.approx(0.969, abs=0.03)
    # The asymmetry is the whole point: they dominate the numerator far more
    # than the denominator, so leaving them in multiplies the answer.
    assert generated_reverts > generated_edits * 1.7


def test_the_rate_a_person_actually_produces(surveyed):
    # 27 reverts in 263,631 hand-written line edits: one in nine thousand. Git
    # has diffs, atomic commits and review, and this is the floor such a medium
    # achieves. The naive number over the same history is 0.149% — 14.5x higher.
    edits, reverts, authored_edits, authored_reverts = totals(surveyed)
    assert authored_reverts / authored_edits == pytest.approx(0.000102, abs=0.00005)
    assert (reverts / edits) / (authored_reverts / authored_edits) > 8


def test_a_results_file_is_not_authored():
    assert not is_authored("projects/03_bfcl/results.json")
    assert not is_authored("nlp-lab/projects/09/results/collocations.json")
    assert not is_authored("data/invoices.csv")
    assert not is_authored("uv.lock")
    assert is_authored("src/revenue/churn.py")
    assert is_authored("README.md")
    assert is_authored("pyproject.toml")
    # A hand-written config that merely lives beside results is still authored.
    assert is_authored("config/settings.json")


def test_most_repositories_contain_no_authored_revert_at_all(surveyed):
    big = [s for s in surveyed if s.authored_edits > 1000]
    assert len(big) >= 30
    clean = [s for s in big if not s.authored_reverts]
    assert len(clean) / len(big) > 0.75  # 28 of 34


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


def test_a_line_removed_and_restored_inside_one_commit_is_not_a_revert():
    # It moved, or the same text appears in two hunks. With -U0 git reports that
    # as a remove/add pair, and counting it was 86% of everything this found.
    history = [
        Edit("c1", 0, "a.py", "timeout = 30  # measured", added=True),
        Edit("c2", 1, "a.py", "timeout = 30  # measured", added=False),
        Edit("c2", 1, "a.py", "timeout = 30  # measured", added=True),
    ]
    assert find_reverts(history) == []


def test_no_real_revert_happens_within_a_single_commit(surveyed):
    gaps = [r.gap for s in surveyed for r in s.authored_reverts]
    assert gaps
    assert min(gaps) >= 1  # undoing is a relation between commits
    assert statistics.median(gaps) == 1  # and usually the very next one
    assert max(gaps) > 5  # though a few come back much later


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


def test_an_empty_history_yields_nothing():
    assert find_reverts([]) == []
