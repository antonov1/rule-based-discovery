from typing import Callable, List, Optional

import networkx as nx
from inductive_miner.cuts import LoopCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import assert_rules_supported, surgical_repair
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
    im_function: Callable[[List[List[str]], ProcessTree], ProcessTree],
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
        unsat_rules = LoopCut.check_rules(rules, [set(), acts])
        if unsat_rules:
            return surgical_repair(log, unsat_rules, im_function, rules)

    parent = ProcessTree(operator=Operator.LOOP)
    proj_rules = (
        LoopCut.project_rules(rules, [set(), {act for trace in log for act in trace}])[
            1
        ]
        if rules
        else None
    )
    assert_rules_supported("In STAU (0):", sublog, proj_rules)

    do_child = im_function(sublog, proj_rules) if proj_rules else im_function(sublog)
    redo_child = ProcessTree()

    add_child(parent=parent, child=do_child)
    add_child(parent=parent, child=redo_child)

    return parent
