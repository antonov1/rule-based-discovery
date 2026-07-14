from typing import List, Set, Tuple

import networkx as nx
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)


def add_child(parent, child):
    child.parent = parent
    parent.children.append(child)


ARTIFICIAL_START = "__ArtificialStart__"
ARTIFICIAL_END = "__ArtificialEnd__"
ARTIFICIAL_NONE_NODE = "ArtificialNoneNode"


def check_acyclic(graph: nx.DiGraph, add_edge: Tuple[str, str]) -> bool:
    graph.add_edge(*add_edge)
    is_acyclic = nx.is_directed_acyclic_graph(graph)
    graph.remove_edge(*add_edge)
    return is_acyclic


def build_cdg(rules: List[AbstractRule], alphabet: Set[str]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(alphabet)
    g.add_node(ARTIFICIAL_START)
    g.add_node(ARTIFICIAL_END)
    for r in rules or []:

        if isinstance(r, InitializationRule):
            g.add_edge(ARTIFICIAL_START, r.target_activity)
            r.target_activity

        elif isinstance(r, EndRule):
            g.add_edge(r.target_activity, ARTIFICIAL_END)
            r.target_activity

        elif (
            isinstance(r, ResponseRule)
            or isinstance(r, PrecedenceRule)
            or isinstance(r, ChainPrecedenceRule)
            or isinstance(r, ChainResponseRule)
        ):
            g.add_edge(r.activity_a, r.activity_b)
        elif isinstance(r, NotSuccessionRule):
            # not ideal but we can always switch their places
            g.add_edge(r.activity_b, r.activity_a)
        elif isinstance(r, RespondedExistenceRule) or isinstance(r, CoExistenceRule):
            # just add them as nodes
            g.add_node(r.activity_a) if r.activity_a not in g.nodes else None
            g.add_node(r.activity_b) if r.activity_b not in g.nodes else None

    # floating components should be connected to initialization_node and end_node
    return g


def build_signed_cdg(
    rules: List[AbstractRule], alphabet: Set[str]
) -> Tuple[nx.DiGraph, nx.DiGraph]:
    positive_graph = build_cdg(rules, alphabet)
    # drop the artificial start and end
    positive_graph.remove_node(ARTIFICIAL_START)
    positive_graph.remove_node(ARTIFICIAL_END)
    negative_graph = nx.DiGraph()
    negative_graph.add_nodes_from(alphabet)
    for r in rules or []:
        if isinstance(r, NotCoExistenceRule):
            negative_graph.add_edge(r.activity_a, r.activity_b)
    return positive_graph, negative_graph
