from typing import Callable, Optional

import networkx as nx
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from utils.directly_follows_graph import DirectlyFollowsGraph


def detect(log: list[list[str]], cut_order: list[type]) -> Optional[str]:
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
    log: list[list[str]],
    dfg: nx.DiGraph,
    cut_order: list[type],
    **kwargs,
) -> Optional[ProcessTree]:
    candidate = detect(log, cut_order=cut_order)
    if candidate is None:
        return None

    # Binary split
    sublogs = project(log, candidate)

    parent = ProcessTree(operator=Operator.PARALLEL)

    add_child(parent, im_function(sublogs[0], ProcessTree()))

    add_child(parent, im_function(sublogs[1], ProcessTree()))

    return parent
