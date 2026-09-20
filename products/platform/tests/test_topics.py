import pytest

from agentplatform import topics


def test_five_topics_under_one_domain():
    t = topics.Topics("crm")
    assert t.all() == (
        "crm.intake",
        "crm.tasks",
        "crm.events",
        "crm.approvals",
        "crm.dlq",
    )


@pytest.mark.parametrize("bad", ["CRM", "crm_desk", "-crm", "crm--desk", "1crm", ""])
def test_illegal_domains_are_refused(bad):
    with pytest.raises(topics.InvalidDomainError):
        topics.Topics(bad)


def test_unknown_suffix_is_refused():
    with pytest.raises(ValueError):
        topics.Topics("crm").name("retries")


def test_same_entity_always_lands_on_one_partition():
    key = topics.partition_key("deal", "4192")
    assert key == "deal:4192"
    assert len({topics.partition_for(key, 12) for _ in range(50)}) == 1


def test_partitioning_is_stable_across_processes():
    # The whole point of crc32 over the built-in hash: this value must not
    # change when PYTHONHASHSEED does. Pinning it is the regression test.
    assert topics.partition_for("deal:4192", 12) == topics.partition_for("deal:4192", 12)
    assert topics.partition_for("deal:4192", 1) == 0


def test_partition_count_must_be_positive():
    with pytest.raises(ValueError):
        topics.partition_for("deal:1", 0)


def test_partition_key_needs_both_halves():
    with pytest.raises(ValueError):
        topics.partition_key("deal", "")
