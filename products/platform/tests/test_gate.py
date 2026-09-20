import pytest

from agentplatform import gate

ISSUED = {"src_a41", "src_b22", "src_c07"}


def test_a_receipted_claim_is_kept():
    r = gate.run([gate.Claim("Acme raised a round", ("src_a41",))], ISSUED)
    assert len(r.kept) == 1
    assert r.dropped == []


def test_a_claim_with_no_receipt_is_dropped():
    r = gate.run([gate.Claim("They are evaluating vendors")], ISSUED)
    assert r.kept == []
    assert r.dropped[0].reason == gate.NO_RECEIPT


def test_an_invented_citation_is_caught():
    # The failure a human reviewer misses: src_z99 looks exactly like a real id.
    r = gate.run([gate.Claim("Budget closes in December", ("src_z99",))], ISSUED)
    assert r.kept == []
    assert gate.FABRICATED in r.dropped[0].reason
    assert "src_z99" in r.dropped[0].reason


def test_one_good_receipt_does_not_excuse_one_invented_one():
    r = gate.run([gate.Claim("Mixed", ("src_a41", "src_z99"))], ISSUED)
    assert r.kept == []


def test_corroboration_requires_distinct_sources():
    same = gate.Claim("Repeated", ("src_a41", "src_a41"))
    assert gate.run([same], ISSUED, min_sources=2).dropped[0].reason == gate.UNDER_CORROBORATED
    both = gate.Claim("Corroborated", ("src_a41", "src_b22"))
    assert len(gate.run([both], ISSUED, min_sources=2).kept) == 1


def test_drop_rate_is_reported():
    r = gate.run(
        [gate.Claim("ok", ("src_a41",)), gate.Claim("bare"), gate.Claim("fake", ("src_z99",))],
        ISSUED,
    )
    assert r.drop_rate == pytest.approx(2 / 3)


def test_an_empty_run_has_no_drop_rate_rather_than_dividing_by_zero():
    assert gate.run([], ISSUED).drop_rate == 0.0


def test_min_sources_must_be_sane():
    with pytest.raises(ValueError):
        gate.run([], ISSUED, min_sources=0)
