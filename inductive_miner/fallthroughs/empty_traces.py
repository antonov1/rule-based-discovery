from typing import Callable, List

import networkx as nx
from inductive_miner.cuts import ExclusiveChoiceCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import repair_mechanism, RepairVariant
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def detect(dfg: nx.DiGraph):
    if "ArtificialNoneNode" in dfg:
        return True
    return False


def project(log: List[List[str]]) -> List[List[str]]:
    return [trace for trace in log if len(trace) > 0]


def apply(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    repair_mode=RepairVariant.TraceLevel,
    **kwargs,
) -> ProcessTree:
    if not detect(dfg):
        return None
    sublog = project(log)
    if not sublog:
        return ProcessTree()  # tau only

    if rules:
        acts = set(act for trace in log for act in trace)
        unsat_rules = ExclusiveChoiceCut.check_rules(rules, [set(), acts])
        if unsat_rules:
            return repair_mechanism(
                log,
                unsat_rules,
                im_function,
                rules,
                repair_mode=repair_mode,
            )
    parent = ProcessTree(operator=Operator.XOR)
    tau_child = ProcessTree()
    add_child(parent=parent, child=tau_child)

    if rules:
        acts = set(act for trace in log for act in trace)
        proj_rules = ExclusiveChoiceCut.project_rules(
            rules, [set(), set(act for trace in log for act in trace)]
        )[1]
        non_tau_child = im_function(sublog, proj_rules, repair_mode=repair_mode)
    else:
        non_tau_child = im_function(sublog)

    add_child(parent=parent, child=non_tau_child)
    return parent
