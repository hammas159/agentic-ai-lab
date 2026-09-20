import pytest

from hermes.domain import Constraint, ConstraintDroppedError, Handoff, prepare, survival, verify


def known():
    return [
        Constraint("c1", "diet", "vegan", hard=True),
        Constraint("c2", "access", "step-free", hard=True),
        Constraint("c3", "seat", "window", hard=False),
    ]


def test_prepare_carries_every_constraint_not_the_relevant_ones():
    handoff = prepare("booking-agent", "find a hotel", known())
    assert handoff.carried == {"c1", "c2", "c3"}
    assert verify(known(), handoff) == []


def test_a_handoff_dropping_a_hard_constraint_is_refused():
    naive = Handoff("booking-agent", "find a hotel", [])
    with pytest.raises(ConstraintDroppedError):
        verify(known(), naive)


def test_the_refusal_names_what_would_have_been_lost():
    naive = Handoff("booking-agent", "find a hotel", [])
    with pytest.raises(ConstraintDroppedError, match="diet=vegan"):
        verify(known(), naive)


def test_dropping_only_a_soft_constraint_is_a_reported_degradation():
    partial = Handoff("booking-agent", "x", [c for c in known() if c.hard])
    lost = verify(known(), partial)
    assert [c.id for c in lost] == ["c3"]


def test_a_handoff_needs_a_target():
    with pytest.raises(ValueError):
        prepare("", "x", known())


def test_survival_is_one_when_nothing_is_dropped():
    chain = [prepare("a", "x", known()), prepare("b", "y", known())]
    assert survival(known(), chain) == 1.0


def test_survival_falls_with_each_lossy_handoff():
    lossy = Handoff("a", "x", [known()[0]])
    assert survival(known(), [lossy]) == pytest.approx(1 / 3)


def test_survival_is_the_intersection_across_the_whole_chain():
    first = Handoff("a", "x", known()[:2])
    second = Handoff("b", "y", known()[1:])
    assert survival(known(), [first, second]) == pytest.approx(1 / 3)


def test_no_constraints_means_nothing_can_be_lost():
    assert survival([], []) == 1.0
