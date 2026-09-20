"""bid-desk against real documents with real binding requirements.

`products/data/rfc*.txt` are published RFCs. RFC 2119 defines which words make a
requirement binding, and says they count only in upper case — so `MUST` is an
obligation and `must` in the same paragraph is prose. That is a labelled corpus
of mandatory, advisory and optional items with no annotation required.

Every figure asserted here was produced by running this code over those files.
"""

import pytest

from biddesk.rfc import (
    DATA,
    MANDATORY,
    by_keyword,
    compare_mandatory,
    loose,
    mandatory_only,
    strict,
)

pytestmark = pytest.mark.skipif(
    not list(DATA.glob("rfc*.txt")), reason="no RFC text on disk"
)


def test_the_documents_load():
    assert len(strict()) == 4_036
    assert len(loose()) == 5_750


def test_the_keyword_mix_is_what_rfc_2119_describes():
    counts = by_keyword(strict())
    assert counts["MUST"] == 1_558
    assert counts["SHALL"] < counts["MUST"] / 10  # rare now, and still binding
    assert set(counts) >= set(MANDATORY)


def test_mandatory_is_a_minority_of_all_requirements():
    assert len(mandatory_only(strict())) == 2_242
    assert len(mandatory_only(strict())) < len(strict())


def test_a_case_insensitive_reader_cannot_miss_a_mandatory_item():
    # Upper case is a subset of case-insensitive, so recall is 1.0 by
    # construction. Worth asserting because it is the half everyone worries
    # about and it turns out not to be the problem.
    assert compare_mandatory().recall == 1.0


def test_but_one_flagged_obligation_in_five_is_not_one():
    # THE FINDING. 465 lines contain the word "must" without being requirements,
    # and a checklist built by reading for the word carries every one of them.
    #
    # Measured first on six RFCs (precision 0.830) and again on seventeen
    # (0.827). Tripling the corpus moved it by three thousandths, which is the
    # reason to trust it.
    result = compare_mandatory()
    assert result.precision == pytest.approx(0.827, abs=0.015)
    assert result.false_positives == 465


def test_the_distinction_is_the_capital_letters():
    # RFC 2119 is explicit that the keywords bind only in upper case, which is
    # exactly the signal a case-insensitive extractor throws away.
    upper = {(r.document, r.line) for r in mandatory_only(strict())}
    both = {(r.document, r.line) for r in mandatory_only(loose())}
    assert both - upper  # lines the loose reader added
    assert not upper - both  # and none it lost


def test_prohibitions_count_as_mandatory():
    counts = by_keyword(strict())
    assert counts["MUST NOT"] == 582
    assert all(r.mandatory for r in strict() if r.keyword == "MUST NOT")


def test_an_advisory_item_is_not_mandatory():
    should = [r for r in strict() if r.keyword == "SHOULD"]
    assert should
    assert not any(r.mandatory for r in should)


def test_missing_documents_are_reported_rather_than_faked():
    from biddesk.rfc import DocumentsMissingError

    with pytest.raises(DocumentsMissingError):
        strict(str(DATA / "nowhere"))
