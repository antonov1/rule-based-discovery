from typing import Callable, List, Optional, Set

import networkx as nx
from inductive_miner.cuts import SequenceCut
from inductive_miner.fallthroughs.fallthrough_utils import (
    add_child,
    ARTIFICIAL_START,
    build_cdg,
)
from inductive_miner.im_utils import repair_behavior
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def detect_groups(rules: List[AbstractRule], alphabet: Set[str]) -> Optional[List[set]]:
    if not alphabet:
        return None

    cdg = build_cdg(rules, alphabet)

    # preference to initialization rules
    head = set(cdg.successors(ARTIFICIAL_START))
    if not head:
        # look in the graph for other potential candidates
        head = {n for n in alphabet if cdg.in_degree(n) == 0}

    body = set(alphabet) - head

    if not head or not body:
        return None

    return [head, body]


def apply(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    **kwargs,
) -> Optional[ProcessTree]:
    alphabet = set(dfg.nodes) - {"ArtificialNoneNode"}
    groups = detect_groups(rules or [], alphabet)

    if groups is None:
        return None

    violations = SequenceCut.check_rules(rules or [], groups)
    if violations:
        repaired = repair_behavior(log, violations, im_function, rules or [])
        if repaired is not None:
            return repaired
        return None

    projections = SequenceCut(dfg).relaxed_projection(log, groups)
    proj_rules = SequenceCut.project_rules(rules, groups) if rules else [None, None]
    parent = ProcessTree(operator=Operator.SEQUENCE)

    for i in range(len(projections)):
        child_rules = proj_rules[i] if proj_rules else None
        child = (
            im_function(projections[i], child_rules)
            if child_rules
            else im_function(projections[i])
        )
        add_child(parent, child)

    return parent
