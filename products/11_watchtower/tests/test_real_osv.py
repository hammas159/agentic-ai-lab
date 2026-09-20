"""watchtower against the real OSV vulnerability database.

`products/data/osv_pypi.zip` is OSV's published export for PyPI: 30,552 real
advisories across 13,587 packages, each carrying the version ranges it applies
to. Every figure asserted here was produced by running this code over that file.
"""

import pytest

from watchtower.osv import OSV_ZIP, Advisory, Window, installed, load, version_key

pytestmark = pytest.mark.skipif(not OSV_ZIP.exists(), reason="OSV export not on disk")


@pytest.fixture(scope="module")
def db():
    return load()


@pytest.fixture(scope="module")
def verdicts(db):
    """Every advisory judged at every boundary version known for its package."""
    fp = fn = agree = 0
    for advisories in db.values():
        candidates = set()
        for adv in advisories:
            for window in adv.windows:
                candidates.add(window.introduced)
                if window.fixed:
                    candidates.add(window.fixed)
        for adv in advisories:
            for version in candidates:
                naive, correct = adv.affects_naively(version), adv.affects(version)
                if naive == correct:
                    agree += 1
                elif naive:
                    fp += 1
                else:
                    fn += 1
    return {"agree": agree, "false_positive": fp, "false_negative": fn}


def test_the_database_loads(db):
    assert len(db) > 13_000
    assert sum(len(a) for a in db.values()) > 30_000


def test_versions_order_numerically():
    assert version_key("1.10.0") > version_key("1.9.0")
    assert version_key("2026.7.22") > version_key("2025.1.1")


def test_a_window_is_half_open():
    window = Window("0.10.0", "0.11.1")
    assert not window.covers("0.9.9")   # before the bug was written
    assert window.covers("0.10.0")      # the version it was introduced in
    assert window.covers("0.11.0")
    assert not window.covers("0.11.1")  # the fix itself is not affected


def test_an_unfixed_window_stays_open():
    assert Window("1.0", None).covers("99.0")


def test_the_shortcut_flags_versions_written_before_the_bug():
    # The concrete case, from a real advisory: open-webui GHSA-2724-6cpj-gf3v
    # affects 0.10.0 up to 0.11.1. Version 0.6.19 predates the vulnerability
    # entirely, and "below the highest fixed version" calls it vulnerable.
    adv = Advisory(
        id="GHSA-2724-6cpj-gf3v",
        package="open-webui",
        summary="",
        windows=[Window("0.10.0", "0.11.1")],
    )
    assert adv.highest_fixed == "0.11.1"
    assert adv.affects_naively("0.6.19")
    assert not adv.affects("0.6.19")


def test_the_shortcut_is_wrong_one_time_in_six(verdicts):
    # THE FINDING. 2.1 million verdicts over 30,552 real advisories.
    total = sum(verdicts.values())
    assert total > 2_000_000
    wrong = verdicts["false_positive"] + verdicts["false_negative"]
    assert wrong / total == pytest.approx(0.154, abs=0.01)


def test_it_errs_overwhelmingly_towards_false_alarms(verdicts):
    total = sum(verdicts.values())
    assert verdicts["false_positive"] / total == pytest.approx(0.142, abs=0.01)
    assert verdicts["false_negative"] / total == pytest.approx(0.012, abs=0.005)
    assert verdicts["false_positive"] > verdicts["false_negative"] * 8


def test_a_version_between_two_windows_is_the_false_negative_case():
    # Two maintained branches: fixed in 1.2, broken again in 2.0, fixed in 2.1.
    # 2.0 is above the highest fixed version, so the shortcut clears it.
    adv = Advisory(
        id="x", package="p", summary="",
        windows=[Window("1.0", "1.2"), Window("2.0", "2.1")],
    )
    assert adv.affects("2.0")
    assert not adv.affects_naively("2.2")
    assert adv.affects_naively("1.1")


def test_this_machine_is_scannable(db):
    here = installed()
    assert len(here) > 10
    covered = [p for p in here if p in db]
    assert covered, "expected at least one installed package to carry an advisory"


def test_a_missing_database_is_reported_rather_than_faked():
    from watchtower.osv import DatabaseMissingError

    with pytest.raises(DatabaseMissingError):
        load(str(OSV_ZIP.parent / "nope.zip"))
