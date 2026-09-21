from typing import List, Optional, Set

import networkx as nx
from inductive_miner.cuts import LoopCut
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator
from rules import AbstractRule


def detect(
    log: List[list[str]],
    start_activities: Set[str],
) -> Optional[List[List[str]]]:
    proj = []

    for trace in log:
        x = 0
        for i in range(1, len(trace)):
            if trace[i] in start_activities:
                proj.append(trace[x:i])
                x = i
        proj.append(trace[x : len(trace)])

    return proj if len(proj) > len(log) else None


def project(
    log: List[List[str]],
    start_activities: Set[str],
) -> Optional[List[List[str]]]:
    return detect(log, start_activities)


def apply(
    log: List[List[str]],
    dfg: nx.DiGraph,
    start_activities: Set[str],
    rules: List[AbstractRule] = None,
    **kwargs,
) -> Optional[Decomposition]:
    acts = list(dfg.nodes)
    sublog = detect(log, start_activities)
    if sublog is None:
        return None

    # Rule Check
    if rules:
        acts = {act for trace in log for act in trace}
        unsat_rules = LoopCut.check_rules(rules, [acts, set()])
        if unsat_rules:
            return unsat_rules

    proj_rules = (
        LoopCut.project_rules(rules, [{act for trace in log for act in trace}, set()])
        if rules
        else None
    )

    if set(proj_rules[0]) == set(rules) and len(sublog) > len(log):
        return None

    projected_log = [sublog, []]
    return Decomposition(
        operator=Operator.LOOP,
        sublogs=projected_log,
        projected_rules=proj_rules,
    )
