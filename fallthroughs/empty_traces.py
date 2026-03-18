from typing import Callable, List

import networkx as nx
from fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def detect(dfg: nx.DiGraph):
    if "ArtificialNoneNode" in dfg:
        return True
    return False


def project(log: List[List[str]]) -> List[List[str]]:
    return [trace for trace in log if len(trace) > 0]


def apply(
    im_function: Callable, log: List[List[str]], dfg: nx.DiGraph, **kwargs
) -> ProcessTree:
    if not detect(dfg):
        return None
    sublog = project(log)
    if not sublog:
        return ProcessTree()  # tau only

    parent = ProcessTree(operator=Operator.XOR)
    tau_child = ProcessTree()
    add_child(parent=parent, child=tau_child)
    non_tau_child = im_function(sublog, ProcessTree())
    add_child(parent=parent, child=non_tau_child)
    return parent
