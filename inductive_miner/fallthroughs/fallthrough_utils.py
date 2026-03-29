from typing import List, Set

import networkx as nx
from rules import (
    AbstractRule,
    EndRule,
    InitializationRule,
    PrecedenceRule,
    ResponseRule,
)


def add_child(parent, child):
    child.parent = parent
    parent.children.append(child)


ARTIFICIAL_START = "__ArtificialStart__"
ARTIFICIAL_END = "__ArtificialEnd__"


def build_cdg(rules: List[AbstractRule], alphabet: Set[str]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(alphabet)
    g.add_node(ARTIFICIAL_START)
    g.add_node(ARTIFICIAL_END)

    for r in rules or []:

        if isinstance(r, InitializationRule):
            g.add_edge(ARTIFICIAL_START, r.target_activity)

        elif isinstance(r, EndRule):
            g.add_edge(r.target_activity, ARTIFICIAL_END)

        elif isinstance(r, ResponseRule) or isinstance(r, PrecedenceRule):
            g.add_edge(r.activity_a, r.activity_b)

    return g
