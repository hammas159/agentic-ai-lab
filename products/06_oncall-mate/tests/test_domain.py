import pytest

from oncall.domain import Alert, collapse, dedupe, reduction


def a(i, service, at, template="upstream timeout after <*>ms"):
    return Alert(f"al_{i}", service, template, at)


def test_a_burst_from_one_service_is_one_incident():
    alerts = [a(1, "checkout", 0), a(2, "checkout", 30), a(3, "checkout", 60)]
    assert len(collapse(alerts)) == 1


def test_a_drip_cannot_chain_past_the_span_cap():
    # Each alert is inside the 120s window of the one before it, for two hours.
    # Without max_span this is a single "critical incident" spanning the afternoon.
    alerts = [a(i, "checkout", i * 100) for i in range(72)]
    incidents = collapse(alerts, window=120, max_span=900)
    assert len(incidents) > 1
    assert all(inc.span <= 900 for inc in incidents)


def test_unrelated_services_do_not_merge_by_default():
    alerts = [a(1, "checkout", 0), a(2, "billing", 10)]
    assert len(collapse(alerts)) == 2


def test_services_can_be_merged_deliberately():
    alerts = [a(1, "checkout", 0), a(2, "billing", 10)]
    assert len(collapse(alerts, same_service_only=False)) == 1


def test_a_gap_wider_than_the_window_starts_a_new_incident():
    alerts = [a(1, "checkout", 0), a(2, "checkout", 500)]
    assert len(collapse(alerts, window=120)) == 2


def test_order_comes_from_the_timestamp_not_the_list():
    alerts = [a(2, "checkout", 60), a(1, "checkout", 0)]
    (incident,) = collapse(alerts)
    assert [x.id for x in incident.alerts] == ["al_1", "al_2"]


def test_an_impossible_window_is_refused():
    with pytest.raises(ValueError):
        collapse([], window=0)
    with pytest.raises(ValueError):
        collapse([], window=120, max_span=10)


def test_dedupe_fingerprints_the_template_not_the_line():
    # Same fault, different host in the message — identical fingerprints.
    alerts = [a(1, "checkout", 0), a(2, "checkout", 30)]
    assert len(dedupe(alerts, repeat_after=300)) == 1


def test_a_different_template_is_a_different_alert():
    alerts = [a(1, "checkout", 0), a(2, "checkout", 30, template="pool exhausted")]
    assert len(dedupe(alerts)) == 2


def test_a_refire_after_the_repeat_window_is_kept():
    alerts = [a(1, "checkout", 0), a(2, "checkout", 400)]
    assert len(dedupe(alerts, repeat_after=300)) == 2


def test_reduction_is_reported():
    alerts = [a(i, "checkout", i * 10) for i in range(10)]
    assert reduction(alerts, collapse(alerts)) == pytest.approx(0.9)


def test_no_alerts_means_no_reduction_rather_than_a_crash():
    assert reduction([], []) == 0.0
