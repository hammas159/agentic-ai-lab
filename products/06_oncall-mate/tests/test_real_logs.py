"""oncall-mate against real production logs.

`products/data/*_2k.log` are Loghub's published samples: real logs from HDFS,
BlueGene/L, an HPC cluster, OpenStack and ZooKeeper. Same size, same templater,
five very different systems.

Every figure asserted here was produced by running this code over those files.
"""

import pytest

from oncall.domain import Alert, collapse, reduction
from oncall.logs import DATA, SYSTEMS, Line, compression, read, template

pytestmark = pytest.mark.skipif(
    not (DATA / "hdfs_2k.log").exists(), reason="Loghub samples not on disk"
)


@pytest.fixture(scope="module")
def lines():
    return read()


def by_system(lines, system):
    return [line for line in lines if line.system == system]


def test_all_five_systems_load(lines):
    assert len(lines) == 10_000
    assert {line.system for line in lines} == set(SYSTEMS)


def test_templating_masks_what_varies_per_occurrence():
    a = template("PacketResponder 1 for block blk_38865049064139660 terminating")
    b = template("PacketResponder 0 for block blk_-6952295868487656571 terminating")
    assert a == b == "PacketResponder <num> for block <blk> terminating"


def test_an_ip_is_not_an_identity():
    assert template("client 10.11.10.1 timed out") == template("client 192.168.0.7 timed out")


def test_the_compression_ratio_spans_two_orders_of_magnitude(lines):
    # THE FINDING. One templater, five identical 2,000-line samples, and the
    # ratio runs from 1.09 to 125. A compression ratio is a property of the log,
    # not of the templater — so a threshold tuned on one system is meaningless
    # on the next.
    ratios = {s: compression(by_system(lines, s)).ratio for s in SYSTEMS}
    assert ratios["hdfs"] == pytest.approx(125.0, abs=0.5)
    assert ratios["bgl"] == pytest.approx(1.09, abs=0.02)
    assert max(ratios.values()) / min(ratios.values()) > 100


def test_hdfs_collapses_two_thousand_messages_into_sixteen(lines):
    c = compression(by_system(lines, "hdfs"))
    assert c.distinct_raw == 2000
    assert c.distinct_templates == 16
    assert c.messages_lost == 1984


def test_bgl_barely_compresses_at_all(lines):
    c = compression(by_system(lines, "bgl"))
    assert c.distinct_templates == 1840
    assert c.ratio < 1.2  # the context problem is not solved here


def test_compression_eats_the_rare_line_first(lines):
    # An incident is made of the message that appeared once. On HDFS, 2,000
    # messages are seen exactly once and 3 templates are; 1,997 singletons stop
    # existing as anything a correlator could point at.
    c = compression(by_system(lines, "hdfs"))
    assert c.raw_seen_once == 2000
    assert c.templates_seen_once == 3
    assert c.rare_lost == 1997


def test_the_corpus_wide_figure_hides_all_of_that(lines):
    # Averaging across systems gives 4.29x and looks unremarkable, which is why
    # the per-system table is the result and the headline number is not.
    c = compression(lines)
    assert c.ratio == pytest.approx(4.29, abs=0.05)
    assert c.rare_lost == 7844


def test_a_drip_of_real_templates_still_cannot_chain_forever(lines):
    # The transitivity guard, on real templates rather than invented ones.
    hdfs = by_system(lines, "hdfs")[:200]
    alerts = [
        Alert(f"al_{i}", "hdfs", line.template, i * 100)
        for i, line in enumerate(hdfs)
    ]
    incidents = collapse(alerts, window=120, max_span=900)
    assert len(incidents) > 1
    assert all(inc.span <= 900 for inc in incidents)
    assert reduction(alerts, incidents) > 0.8


def test_levels_are_read_from_the_line(lines):
    assert Line("hdfs", 0, "081109 203615 148 INFO dfs.DataNode: x").level == "INFO"
    assert Line("bgl", 0, "RAS KERNEL FATAL something broke").level == "FATAL"


def test_missing_logs_are_reported_rather_than_faked():
    from oncall.logs import LogsMissingError

    with pytest.raises(LogsMissingError):
        read(str(DATA / "nowhere"))
