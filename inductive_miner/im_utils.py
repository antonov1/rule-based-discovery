from typing import Callable, List

from inductive_miner.cuts import LoopCut
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule


def add_child(parent, child):
    child.parent = parent
    parent.children.append(child)


def intersection_of_logs(logs: List[List[str]]) -> List[str]:
    if not logs:
        return []
    intersection = logs[0]
    for log in logs[1:]:
        # keep only traces that are in both logs
        intersection = [trace for trace in intersection if trace in log]
    return intersection


def base_cases(
    log: List[List[str]],
    process_tree: ProcessTree,
    dfg_graph,
    im_function: Callable = None,
    rules: List[AbstractRule] = None,
    **kwargs,
):
    """
    Handle inductive miner base cases.

    Cases:
    - No nodes  -> return tau.
    - One real activity node (optionally plus ArtificialNoneNode):
        - self-loop + empty trace -> LOOP(tau, activity)
        - self-loop only        -> LOOP(activity, tau)
        - no self-loop          -> activity leaf
    - Otherwise: not a base case, raise an error.
    """
    nodes = set(dfg_graph.nodes)

    if "ArtificialNoneNode" in nodes:
        raise Exception(f"Base case error: log has empty traces.")

    if not nodes:
        return process_tree

    if len(nodes) == 1:
        return _build_single_activity_tree(log, dfg_graph, nodes, im_function, rules)

    raise Exception(
        f"Base case error: log has multiple activities but no cut was found."
    )


def _build_single_activity_tree(
    log, dfg_graph, nodes, im_function, rules
) -> ProcessTree:
    if not nodes:
        return ProcessTree()  # Tau

    activity = nodes.pop()

    if not dfg_graph.has_edge(activity, activity):
        return ProcessTree(label=activity)

    has_empty_trace = [] in log
    if has_empty_trace:
        if rules:
            group_0 = set()
            group_1 = set(activity)
            unsat_rules = LoopCut.check_rules(rules, [group_0, group_1])
            if len(unsat_rules) > 0:
                return repair_behavior(log, unsat_rules, im_function, rules)

        return _build_loop_tree(do_first=None, redo=activity)
    if rules:
        group_0 = set(activity)
        group_1 = set()
        unsat_rules = LoopCut.check_rules(rules, [group_0, group_1])
        if len(unsat_rules) > 0:
            return repair_behavior(log, unsat_rules, im_function, rules)

    return _build_loop_tree(do_first=activity, redo=None)


def _build_loop_tree(do_first=None, redo=None) -> ProcessTree:
    """
    Build a LOOP tree with two children.
    Use None to indicate a tau child.
    """
    root = ProcessTree(operator=Operator.LOOP)

    first_child = ProcessTree() if do_first is None else ProcessTree(label=do_first)
    second_child = ProcessTree() if redo is None else ProcessTree(label=redo)
    first_child.parent = root
    second_child.parent = root
    root.children.extend([first_child, second_child])

    return root


def repair_behavior(
    log,
    unsat_rules: List[AbstractRule],
    im_function: Callable,
    original_rules: List[AbstractRule],
):
    sat_traces = [[] for _ in range(len(unsat_rules))]
    for i in range(len(unsat_rules)):
        rule = unsat_rules[i]
        sublog = rule.apply(log)
        sat_traces[i] = sublog
    intersection = intersection_of_logs(sat_traces)
    print(f"Original log was: {log}, repaired log is: {intersection}")
    if len(intersection) == len(log):
        # No progress, continue trying
        return None
    if len(intersection) > 0:
        return im_function(intersection, original_rules)
    else:
        return ProcessTree()  # Tau
