from typing import Callable, List

import networkx as nx
from inductive_miner.cuts import ConcurrentCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import repair_behavior
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def detect(log: List[List[str]], rules: List[AbstractRule]):

    candidate_activities = set(log[0])
    for trace in log:
        for act in list(candidate_activities):
            if trace.count(act) != 1:
                candidate_activities.remove(act)
    candidates = sorted(list(candidate_activities))
    return candidates[0] if len(candidates) else None


def project(log: List[List[str]], candidate: str) -> List[List[str]]:
    new_log = [[e for e in trace if e != candidate] for trace in log]
    new_log = [trace for trace in new_log if len(trace)]
    return new_log


def apply(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    **kwargs,
):
    candidate = detect(log, rules)
    if not candidate:
        return None
    acts = list(dfg.nodes)

    if rules:
        acts = set(act for trace in log for act in trace)
        acts = acts - {candidate}
        unsat_rules = ConcurrentCut.check_rules(rules, [candidate, acts])
        if unsat_rules:
            return repair_behavior(log, unsat_rules, im_function, rules)

    # Concurrent Cut (Parallel)
    parent = ProcessTree(operator=Operator.PARALLEL)
    proj_rules = (
        ConcurrentCut.project_rules(
            rules, [candidate, set(act for trace in log for act in trace) - {candidate}]
        )[1]
        if rules
        else None
    )
    add_child(parent=parent, child=ProcessTree(label=candidate))
    # Get rid of candidates
    projected_log = project(log, candidate=candidate)
    add_child(
        parent=parent,
        child=(
            im_function(projected_log, proj_rules)
            if proj_rules
            else im_function(projected_log)
        ),
    )
    return parent
