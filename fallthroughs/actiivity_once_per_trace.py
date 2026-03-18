from typing import Callable, List

import networkx as nx
from fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def detect(log: List[List[str]]):
    candidate_activities = set(log[0])
    for trace in log:
        for act in list(candidate_activities):
            if trace.count(act) != 1:
                candidate_activities.remove(act)
    candidates = sorted(list(candidate_activities))
    return candidates if len(candidates) else None


def project(log: List[List[str]], candidate: str) -> List[List[str]]:
    new_log = [[e for e in trace if e != candidate] for trace in log]
    return new_log


def apply(im_function: Callable, log: List[List[str]], dfg: nx.DiGraph, **kwargs):
    candidates = detect(log)
    if not candidates:
        return None
    candidate = candidates[0]
    acts = list(dfg.nodes)

    if "ArtificialNoneNode" in acts:
        raise ValueError("Empty Trace detected in Activity-Once-Per-Trace!")
    parent = ProcessTree(operator=Operator.PARALLEL)
    candidate_child = ProcessTree(label=candidate)
    add_child(parent=parent, child=candidate_child)
    sublog = project(log, candidate)
    other_child = im_function(sublog, ProcessTree())
    add_child(parent=parent, child=other_child)
    return parent
