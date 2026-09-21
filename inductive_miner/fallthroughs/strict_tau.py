from typing import List, Optional

import networkx as nx
from inductive_miner.cuts import LoopCut
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def detect(
    log: list[list[str]],
    start_activities: set[str],
    end_activities: set[str],
) -> Optional[list[list[str]]]:
    proj = []

    for trace in log:
        x = 0
        for i in range(1, len(trace)):
            if trace[i] in start_activities and trace[i - 1] in end_activities:
                proj.append(trace[x:i])
                x = i
        proj.append(trace[x : len(trace)])

    return proj if len(proj) > len(log) else None


def project(
    log: list[list[str]], start_activities: set[str], end_activities: set[str]
) -> Optional[list[list[str]]]:
    return detect(log, start_activities, end_activities)


def apply(
    log: list[list[str]],
    dfg: nx.DiGraph,
    start_activities: set[str],
    end_activities: set[str],
    rules: List[AbstractRule] = None,
    **kwargs,
) -> Optional[ProcessTree]:
    acts = list(dfg.nodes)
    sublog = detect(log, start_activities, end_activities)
    if sublog is None:
        return None

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
    if rules:
        if set(proj_rules[0]) == set(rules) and len(sublog) > len(log):
            return None
    # assert_rules_supported("In STAU (0):", sublog, proj_rules)

    projections = [sublog, []]
    return Decomposition(
        operator=Operator.LOOP,
        sublogs=projections,
        projected_rules=proj_rules,
    )
