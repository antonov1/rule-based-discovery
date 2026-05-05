from typing import Callable, List, Optional, Set

import networkx as nx
from inductive_miner.cuts import LoopCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import assert_rules_supported, repair_mechanism
from pm4py.objects.process_tree.obj import Operator, ProcessTree
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
    im_function: Callable[[List[List[str]], ProcessTree], ProcessTree],
    log: List[List[str]],
    dfg: nx.DiGraph,
    start_activities: Set[str],
    rules: List[AbstractRule] = None,
    rule_strictness=1,
    **kwargs,
) -> Optional[ProcessTree]:
    acts = list(dfg.nodes)
    sublog = detect(log, start_activities)
    if sublog is None:
        return None

    # Rule Check
    if rules:
        acts = {act for trace in log for act in trace}
        unsat_rules = LoopCut.check_rules(rules, [set(), acts])
        rule_conf = 1 - len(unsat_rules) / len(rules)
        if rule_conf < rule_strictness:
            return repair_mechanism(
                log, unsat_rules, im_function, rules, rule_strictness=rule_strictness
            )

    parent = ProcessTree(operator=Operator.LOOP)

    proj_rules = (
        LoopCut.project_rules(rules, [set(), {act for trace in log for act in trace}])[
            1
        ]
        if rules
        else None
    )
    assert_rules_supported("In TAU (0):", sublog, proj_rules)

    do_child = (
        im_function(sublog, proj_rules, rule_strictness=rule_strictness)
        if proj_rules
        else im_function(sublog)
    )
    redo_child = ProcessTree()

    add_child(parent=parent, child=do_child)
    add_child(parent=parent, child=redo_child)

    return parent
