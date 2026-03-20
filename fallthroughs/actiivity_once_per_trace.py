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
    return candidates[0] if len(candidates) else None


def project(log: List[List[str]], candidate: str) -> List[List[str]]:
    new_log = [[e for e in trace if e != candidate] for trace in log]
    new_log = [trace for trace in new_log if len(trace)]
    return new_log


def apply(im_function: Callable, log: List[List[str]], dfg: nx.DiGraph, **kwargs):
    candidate = detect(log)
    if not candidate:
        return None
    acts = list(dfg.nodes)

    if "ArtificialNoneNode" in acts:
        raise ValueError("Empty Trace detected in Activity-Once-Per-Trace!")

    parent = ProcessTree(operator=Operator.PARALLEL)
    add_child(parent=parent, child=ProcessTree(label=candidate))
    # Get rid of candidates
    projected_log = project(log, candidate=candidate)
    add_child(parent=parent, child=im_function(projected_log, ProcessTree()))
    return parent
