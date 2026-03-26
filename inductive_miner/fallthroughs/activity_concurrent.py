from typing import Callable, List, Optional

from inductive_miner.cuts import ConcurrentCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import repair_behavior
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule
from utils.directly_follows_graph import DirectlyFollowsGraph


def detect(log: List[List[str]], cut_order: List[type]) -> Optional[str]:
    if not log:
        return None

    candidates = sorted({e for trace in log for e in trace})

    for candidate in candidates:
        # projection
        proj = [[e for e in trace if e != candidate] for trace in log]
        # proj = [trace for trace in proj if len(trace)]

        dfg_proj = DirectlyFollowsGraph(proj).graph
        if len(dfg_proj.nodes) == 0:
            continue

        for cut_cls in cut_order:
            cut_instance = cut_cls(dfg_proj)
            groups = cut_instance.discover()
            if groups is not None:
                # We found an activity that is concurrent to a structured process.
                return candidate

    return None


def project(log: list[list[str]], candidate: str) -> list[list[list[str]]]:
    log_a = [[e for e in trace if e == candidate] for trace in log]
    log_other = [[e for e in trace if e != candidate] for trace in log]
    return [log_a, log_other]


def apply(
    im_function: Callable,
    log: List[List[str]],
    cut_order: List[type],
    rules: List[AbstractRule] = None,
    **kwargs,
) -> Optional[ProcessTree]:
    candidate = detect(log, cut_order=cut_order)
    if candidate is None:
        return None
    #  Rule Check
    if rules:
        acts = set(act for trace in log for act in trace)
        unsat_rules = ConcurrentCut.check_rules(rules, [set(), acts])
        if unsat_rules:
            return repair_behavior(log, unsat_rules, im_function, rules)

    # Binary split
    sublogs = project(log, candidate)

    parent = ProcessTree(operator=Operator.PARALLEL)
    if rules:
        group_0 = set(act for trace in sublogs[0] for act in trace)
        group_1 = set(act for trace in sublogs[1] for act in trace)
        proj_rules = ConcurrentCut.project_rules(rules, [group_0, group_1])
        add_child(parent, im_function(sublogs[0], proj_rules[0]))
        add_child(parent, im_function(sublogs[1], proj_rules[1]))
    else:
        add_child(parent, im_function(sublogs[0]))

        add_child(parent, im_function(sublogs[1]))

    return parent
