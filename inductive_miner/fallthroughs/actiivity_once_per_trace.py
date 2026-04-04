from typing import Callable, List

import networkx as nx
from inductive_miner.cuts import ConcurrentCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule, ExistenceRule


def detect_based_on_rules(log: List[List[str]], rules: List[AbstractRule]):
    alphabet = set([e for trace in log for e in trace])
    candidates = []
    for r in rules:
        if isinstance(r, ExistenceRule):
            candidates.append(r.target_activity)
    candidates = sorted(set(candidates))
    for c in candidates:
        unsat_rules = ConcurrentCut.check_rules(rules, [{c}, alphabet - {c}])
        if not unsat_rules:
            return c
    return None


def detect(log: List[List[str]], rules: List[AbstractRule] = None):
    candidate_activities = set(log[0])
    for trace in log:
        for act in list(candidate_activities):
            if trace.count(act) != 1:
                candidate_activities.remove(act)
    candidates = sorted(list(candidate_activities))
    if rules:
        alphabet = set([e for trace in log for e in trace])

        for c in candidates:
            unsat_rules = ConcurrentCut.check_rules(rules, [{c}, alphabet - {c}])
            if not unsat_rules:
                return c
        return detect_based_on_rules(log, rules)

    return candidates[0] if len(candidates) else None


def project(log: List[List[str]], candidate: str) -> List[List[str]]:

    new_log = [[e for e in trace if e != candidate] for trace in log]
    new_log = [trace for trace in new_log if len(trace)]
    remaining_log = [[e for e in trace if e == candidate] for trace in log]
    return remaining_log, new_log


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
        acts = {act for trace in log for act in trace} - {candidate}
        unsat_rules = ConcurrentCut.check_rules(rules, [{candidate}, acts])
        if unsat_rules:
            return None

    # Concurrent Cut (Parallel)
    parent = ProcessTree(operator=Operator.PARALLEL)
    proj_rules = (
        ConcurrentCut.project_rules(
            rules,
            [{candidate}, {act for trace in log for act in trace} - {candidate}],
        )
        if rules
        else None
    )
    # Get rid of candidates
    projected_logs = project(log, candidate=candidate)
    print(projected_logs)
    print(proj_rules)

    add_child(
        parent=parent,
        child=(
            im_function(projected_logs[0], proj_rules[0])
            if proj_rules
            else im_function(projected_logs[0])
        ),
    )
    add_child(
        parent=parent,
        child=(
            im_function(projected_logs[1], proj_rules[1])
            if proj_rules
            else im_function(projected_logs[1])
        ),
    )
    return parent
