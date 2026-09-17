from typing import List

from inductive_miner.cuts import ExclusiveChoiceCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def project(log: List[List[str]]) -> List[List[str]]:
    return [trace for trace in log if len(trace) > 0]


def apply(
    log: List[List[str]],
    rules: List[AbstractRule] = None,
    **kwargs,
) -> Decomposition:
    sublog = project(log)
    if not sublog:
        return Decomposition(
            operator=Operator.XOR,
            sublogs=[[], []],
            projected_rules=None,
        )

    if rules:
        acts = set(act for trace in log for act in trace)
        unsat_rules = ExclusiveChoiceCut.check_rules(rules, [set(), acts])
        if unsat_rules:
            return unsat_rules
    parent = ProcessTree(operator=Operator.XOR)
    tau_child = ProcessTree()
    add_child(parent=parent, child=tau_child)

    acts = set(act for trace in log for act in trace)
    proj_rules = (
        ExclusiveChoiceCut.project_rules(
            rules, [set(), set(act for trace in log for act in trace)]
        )
        if rules
        else None
    )

    return Decomposition(
        operator=Operator.XOR, sublogs=[[], sublog], projected_rules=proj_rules
    )
