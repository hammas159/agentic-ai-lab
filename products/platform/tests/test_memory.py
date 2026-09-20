import pytest

from agentplatform.memory import Fact, Outcome, Semantic


def test_a_new_fact_is_stored():
    m = Semantic()
    assert m.write(Fact("ayesha", "role", "Head of Payments", "src_b22")).stored
    assert len(m) == 1


def test_the_same_fact_twice_is_a_duplicate_not_a_second_row():
    m = Semantic()
    m.write(Fact("ayesha", "role", "Head of Payments", "src_b22"))
    again = m.write(Fact("ayesha", "role", "Head of Payments", "src_c07"))
    assert again.outcome is Outcome.DUPLICATE
    assert len(m) == 1


def test_a_contradiction_is_returned_rather_than_stored():
    m = Semantic()
    m.write(Fact("ayesha", "role", "Head of Payments", "src_b22"))
    clash = m.write(Fact("ayesha", "role", "CTO", "src_c07"))
    assert clash.outcome is Outcome.CONTRADICTS
    assert clash.existing.value == "Head of Payments"
    assert m.get("ayesha", "role").value == "Head of Payments"


def test_propose_never_mutates():
    m = Semantic()
    m.propose(Fact("ayesha", "role", "CTO", "src_c07"))
    assert len(m) == 0


def test_a_soft_contradiction_can_be_resolved_deliberately():
    m = Semantic(hard={"allergy"})
    m.write(Fact("ayesha", "role", "Head of Payments", "src_b22"))
    m.resolve(Fact("ayesha", "role", "CTO", "src_c07"))
    assert m.get("ayesha", "role").value == "CTO"


def test_a_hard_constraint_is_never_auto_resolved():
    # langgraph-lab 05: dropping a constraint on handoff took safety from
    # 100% to 20%. A hard predicate is the one a person has to settle.
    m = Semantic(hard={"allergy"})
    m.write(Fact("patient_881", "allergy", "penicillin", "evt_2288"))
    with pytest.raises(PermissionError):
        m.resolve(Fact("patient_881", "allergy", "none", "note_12"))
    assert m.get("patient_881", "allergy").value == "penicillin"
