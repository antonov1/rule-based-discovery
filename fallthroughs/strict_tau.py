from typing import Callable, List, Optional

import networkx as nx
from fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree


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
    **kwargs
) -> Optional[ProcessTree]:
    acts = list(dfg.nodes)
    if "ArtificialNoneNode" in acts:
        raise ValueError("Empty Trace detected in Strict-Tau!")

    sublog = detect(log, start_activities, end_activities)
    if sublog is None:
        return None

    parent = ProcessTree(operator=Operator.LOOP)

    do_child = im_function(sublog, ProcessTree())
    redo_child = ProcessTree()

    add_child(parent=parent, child=do_child)
    add_child(parent=parent, child=redo_child)

    return parent
