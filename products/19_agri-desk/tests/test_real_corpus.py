"""agri-desk against the real GenBank corpus.

`products/data/clcuv.gb` is 532 KB of real Cotton leaf curl virus records from
NCBI, committed for offline reproduction. Every number asserted here was
produced by running this code over that file.
"""

import pytest

from agridesk.domain import collapse_clonal, distinct_variants, emerging, false_alarm_rate
from agridesk.genbank import read
from agridesk.sources import DATA, batches, corpus, isolates, surveillance

pytestmark = pytest.mark.skipif(not DATA.exists(), reason="corpus not on disk")

WINDOW = 7518  # the median collection day in this corpus


def test_the_corpus_parses():
    records = corpus()
    assert len(records) == 60
    assert all(r.sequence for r in records)
    assert all(r.accession for r in records)


def test_geo_loc_name_is_read_not_the_retired_country_field():
    # GenBank renamed /country to /geo_loc_name. Reading only the old name
    # leaves every site "unknown", which silently merges every place into one
    # stratum and breaks both collapsing and emergence.
    sites = {r.site for r in corpus()}
    assert sites == {"Pakistan", "India", "China"}


def test_the_documented_eight_genome_submission_is_present():
    # clcuv-surveillance/haplotype.py records this case by accession:
    # ON312781-ON312788, eight genomes, one submission, one field, one
    # haplotype. The accession prefix alone spans two submissions, so filter on
    # the label.
    s2 = [r for r in corpus() if r.isolate.startswith("CLCMV/S2-")]
    assert sorted(r.accession for r in s2) == [f"ON3127{n}" for n in range(81, 89)]
    assert {r.submission for r in s2} == {"CLCMV/S"}
    assert len({r.sequence for r in s2}) == 1  # all eight identical


def test_the_neighbouring_submission_is_clonal_too():
    nia = [r for r in corpus() if r.isolate.startswith("CLCMV/NIA-")]
    assert len(nia) == 5
    assert len({r.sequence for r in nia}) == 1


def test_collapsing_removes_a_third_of_the_corpus():
    iso = isolates()
    assert distinct_variants(iso, collapse=False) == 60
    assert distinct_variants(iso, collapse=True) == 41
    # 19 of 60 records are a sequence already seen at the same site.


def test_the_largest_clonal_group_is_the_documented_one():
    clonal = sorted(
        (c for c in collapse_clonal(isolates()) if c.clonal),
        key=lambda c: -c.size,
    )
    assert [c.size for c in clonal] == [8, 5, 3, 3, 3, 2, 2]
    assert clonal[0].size == 8


def test_every_naive_emergence_call_is_spurious():
    # THE FINDING. Ten distinct sequences appear in the window and look like
    # emerging variants. Requiring a variant to show at more than one site
    # leaves none of them standing.
    iso = isolates()
    assert len(emerging(iso, WINDOW, min_sites=1)) == 10
    assert emerging(iso, WINDOW, min_sites=2) == []
    assert false_alarm_rate(iso, WINDOW, min_sites=2) == 1.0


def test_receipts_are_one_per_observation_not_one_per_record():
    # Handing the gate 60 receipts for 41 observations is the same
    # double-counting the product exists to catch, moved into the evidence list.
    receipts = surveillance({})
    assert len(receipts) == 41
    assert len(set(receipts)) == 41
    assert all(r in {x.accession for x in corpus()} for r in receipts)


def test_batches_are_the_sampling_unit():
    assert len(batches({})) == 29
    assert "CLCMV/S" in batches({})


def test_a_missing_corpus_is_reported_rather_than_faked():
    from agridesk.sources import CorpusMissingError

    with pytest.raises(CorpusMissingError):
        corpus(str(DATA.parent / "does-not-exist.gb"))


def test_a_record_without_a_sequence_is_skipped_not_guessed():
    text = "LOCUS x\nACCESSION XX000001\nORIGIN\n//\n"
    tmp = DATA.parent / "_tmp_empty.gb"
    tmp.write_text(text, encoding="utf-8")
    try:
        assert read(tmp) == []
    finally:
        tmp.unlink()
