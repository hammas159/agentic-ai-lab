import pytest

from swarmlab.domain import (
    Cell,
    ToolCall,
    Write,
    conflicting_writes,
    duplicate_calls,
    turning_point,
)


def test_the_same_call_twice_is_one_duplicate():
    calls = [
        ToolCall("a1", "fetch", {"url": "x", "depth": 1}, 1),
        ToolCall("a2", "fetch", {"url": "x", "depth": 1}, 2),
    ]
    assert duplicate_calls(calls) == 1


def test_argument_order_does_not_make_two_distinct_calls():
    calls = [
        ToolCall("a1", "fetch", {"url": "x", "depth": 1}, 1),
        ToolCall("a2", "fetch", {"depth": 1, "url": "x"}, 2),
    ]
    assert duplicate_calls(calls) == 1


def test_different_arguments_are_different_calls():
    calls = [
        ToolCall("a1", "fetch", {"url": "x"}, 1),
        ToolCall("a2", "fetch", {"url": "y"}, 2),
    ]
    assert duplicate_calls(calls) == 0


def test_one_agent_repeating_itself_still_counts():
    calls = [ToolCall("a1", "fetch", {"url": "x"}, i) for i in range(3)]
    assert duplicate_calls(calls) == 2


def test_two_agents_writing_different_values_is_a_conflict():
    writes = [
        Write("a1", "deal_1", "amount", 100, 1),
        Write("a2", "deal_1", "amount", 200, 2),
    ]
    (conflict,) = conflicting_writes(writes)
    assert conflict.agents == ("a1", "a2")


def test_two_agents_writing_the_same_value_is_contention_not_conflict():
    writes = [
        Write("a1", "deal_1", "amount", 100, 1),
        Write("a2", "deal_1", "amount", 100, 2),
    ]
    assert conflicting_writes(writes) == []


def test_one_agent_changing_its_own_mind_is_not_a_conflict():
    writes = [
        Write("a1", "deal_1", "amount", 100, 1),
        Write("a1", "deal_1", "amount", 200, 2),
    ]
    assert conflicting_writes(writes) == []


def test_different_fields_do_not_collide():
    writes = [
        Write("a1", "deal_1", "amount", 100, 1),
        Write("a2", "deal_1", "stage", "closing", 2),
    ]
    assert conflicting_writes(writes) == []


def test_a_cell_needs_three_repeats_before_it_is_reportable():
    cell = Cell(5, "flat", successes=[True, False], tokens=[10, 20])
    assert not cell.reportable
    cell.successes.append(True)
    cell.tokens.append(30)
    assert cell.reportable
    assert cell.success_rate == pytest.approx(2 / 3)


def test_a_cell_with_no_repeats_refuses_to_report_a_rate():
    with pytest.raises(ValueError):
        _ = Cell(1, "flat").success_rate


def test_an_unknown_topology_is_refused():
    with pytest.raises(ValueError):
        Cell(1, "mesh")


def test_the_turning_point_is_where_success_first_falls():
    cells = [
        Cell(1, "flat", [True] * 3, [10] * 3),
        Cell(3, "flat", [True] * 3, [30] * 3),
        Cell(8, "flat", [True, False, False], [90] * 3),
    ]
    assert turning_point(cells) == 8


def test_no_turning_point_is_itself_a_result():
    cells = [
        Cell(1, "flat", [True] * 3, [10] * 3),
        Cell(3, "flat", [True] * 3, [30] * 3),
    ]
    assert turning_point(cells) is None


def test_unreportable_cells_are_excluded_from_the_curve():
    cells = [
        Cell(1, "flat", [True] * 3, [10] * 3),
        Cell(3, "flat", [False], [30]),
    ]
    assert turning_point(cells) is None
