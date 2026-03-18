from typing import Callable, Optional

import networkx as nx
from fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from utils.directly_follows_graph import DirectlyFollowsGraph


def detect(log: list[list[str]], cut_order: list[type]) -> Optional[str]:
    if not log:
        return None

    candidates = sorted({e for trace in log for e in trace})
    for candidate in sorted(candidates):
        proj = [[e for e in trace if e != candidate] for trace in log]
        proj = [trace for trace in proj if len(trace)]

        dfg_proj = DirectlyFollowsGraph(proj).graph
        for cut_cls in cut_order:
            cut_instance = cut_cls(dfg_proj)
            groups = cut_instance.discover()
            if groups is not None:
                return candidate

    return None


def project(log: list[list[str]], candidate: str) -> list[list[list[str]]]:
    proj = []
    proj_act = []

    for trace in log:
        proj.append([e for e in trace if e != candidate])
        proj_act.append(([e for e in trace if e == candidate]))

    return [proj, proj_act]


def apply(
    im_function: Callable[[list[list[str]], ProcessTree], ProcessTree],
    log: list[list[str]],
    dfg: nx.DiGraph,
    cut_order: list[type],
    **kwargs
) -> Optional[ProcessTree]:
    candidate = detect(log, cut_order=cut_order)
    if candidate is None:
        return None

    acts = list(dfg.nodes)
    if "ArtificialNoneNode" in acts:
        raise ValueError("Empty Trace detected in Activity-Concurrent!")

    sublogs = project(log, candidate)

    parent = ProcessTree(operator=Operator.PARALLEL)

    candidate_child = im_function(sublogs[1], ProcessTree())
    add_child(parent=parent, child=candidate_child)

    other_child = im_function(sublogs[0], ProcessTree())
    add_child(parent=parent, child=other_child)

    return parent
