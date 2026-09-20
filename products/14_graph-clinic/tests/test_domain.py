import pytest

from graphclinic.domain import Edge, contradictions, reachable, shortest, traverse


def graph():
    return [
        Edge("pneumonia", "treated_with", "ceftriaxone", "doc_1"),
        Edge("ceftriaxone", "contraindicated_in", "penicillin_allergy", "doc_2"),
        Edge("pneumonia", "presents_with", "fever", "doc_3"),
    ]


def test_an_edge_without_a_source_is_refused():
    with pytest.raises(ValueError):
        Edge("a", "rel", "b", "")


def test_a_one_hop_walk_finds_the_direct_neighbours():
    paths = traverse(graph(), "pneumonia", max_hops=1)
    assert {p.nodes[-1] for p in paths} == {"ceftriaxone", "fever"}


def test_a_two_hop_walk_reaches_the_contraindication():
    assert "penicillin_allergy" in reachable(graph(), "pneumonia", max_hops=2)


def test_the_hop_cap_is_enforced():
    assert "penicillin_allergy" not in reachable(graph(), "pneumonia", max_hops=1)


def test_a_zero_hop_walk_is_refused():
    with pytest.raises(ValueError):
        traverse(graph(), "pneumonia", max_hops=0)


def test_every_path_carries_the_documents_it_crossed():
    path = shortest(graph(), "pneumonia", "penicillin_allergy")
    assert path is not None
    assert path.sources == ("doc_1", "doc_2")
    assert path.hops == 2


def test_an_unreachable_target_returns_nothing_rather_than_a_guess():
    assert shortest(graph(), "pneumonia", "diabetes") is None


def test_a_cycle_terminates():
    cyclic = [
        Edge("a", "relates_to", "b", "doc_1"),
        Edge("b", "relates_to", "a", "doc_2"),
    ]
    paths = traverse(cyclic, "a", max_hops=6)
    assert [p.nodes for p in paths] == [("a", "b")]


def test_two_documents_disagreeing_is_reported():
    edges = [
        Edge("pneumonia", "treated_with", "ceftriaxone", "doc_1"),
        Edge("pneumonia", "treated_with", "amoxicillin", "doc_9"),
    ]
    (pair,) = contradictions(edges)
    assert {pair[0].source, pair[1].source} == {"doc_1", "doc_9"}


def test_one_document_listing_two_options_is_not_a_contradiction():
    edges = [
        Edge("pneumonia", "treated_with", "ceftriaxone", "doc_1"),
        Edge("pneumonia", "treated_with", "amoxicillin", "doc_1"),
    ]
    assert contradictions(edges) == []


def test_agreement_across_documents_is_not_a_contradiction():
    edges = [
        Edge("pneumonia", "treated_with", "ceftriaxone", "doc_1"),
        Edge("pneumonia", "treated_with", "ceftriaxone", "doc_9"),
    ]
    assert contradictions(edges) == []
