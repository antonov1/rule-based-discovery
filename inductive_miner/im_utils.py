from enum import Enum
from typing import Callable, List

from inductive_miner.cuts import LoopCut
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AbstractRule, EndRule, ExistenceRule, InitializationRule


class RepairVariant(Enum):
    EventLevel = "event_level"
    TraceLevel = "trace_level"


class LogRepairMechanism(Enum):
    BinaryRepair = "binary"
    SupportRepair = "support"


REPAIR_VARIANT = RepairVariant.EventLevel


def acts_of(log):
    return {e for trace in log for e in trace}


def assert_rules_supported(where: str, log, rules):
    acts = acts_of(log)
    bad = []

    for r in rules or []:
        if hasattr(r, "target_activity"):
            if r.target_activity not in acts:
                bad.append((str(r), acts))
        elif hasattr(r, "activity_a") and hasattr(r, "activity_b"):
            if r.activity_a not in acts or r.activity_b not in acts:
                bad.append((str(r), acts))

    if bad:
        raise Exception(
            f"[{where}] unsupported rules: {bad} for acts={acts} and log_head={log[:5]}"
        )


def normalize_tree(node):
    if node is None:
        return None

    if not getattr(node, "children", None):
        return node

    associative_ops = {
        Operator.SEQUENCE,
        Operator.XOR,
        Operator.PARALLEL,
    }

    new_children = []
    for child in node.children:
        child = normalize_tree(child)
        if child is None:
            continue

        if node.operator in associative_ops and child.operator == node.operator:
            for grandchild in child.children:
                grandchild.parent = node
                new_children.append(grandchild)
        else:
            child.parent = node
            new_children.append(child)

    node.children = new_children

    return node


def add_child(parent, child):
    if child is None:
        return

    associative_ops = {
        Operator.SEQUENCE,
        Operator.XOR,
        Operator.PARALLEL,
    }

    if (
        parent is not None
        and parent.operator in associative_ops
        and child.operator == parent.operator
    ):
        for grandchild in child.children:
            grandchild.parent = parent
            parent.children.append(grandchild)
    else:
        child.parent = parent
        parent.children.append(child)


def intersection_of_logs(logs: List[List[List[str]]]) -> List[str]:
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
            if unsat_rules:
                return repair_mechanism(
                    log,
                    unsat_rules,
                    im_function,
                    rules,
                )

        return _build_loop_tree(do_first=None, redo=activity)
    if rules:
        group_0 = set(activity)
        group_1 = set()
        unsat_rules = LoopCut.check_rules(rules, [group_0, group_1])

        if unsat_rules:
            return repair_mechanism(log, unsat_rules, im_function, rules)

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


def supported_rules(log, rules):
    if not rules:
        return []

    acts = {a for trace in log for a in trace}
    filtered = []

    for rule in rules:
        if hasattr(rule, "target_activity"):
            if rule.target_activity in acts:
                filtered.append(rule)
        elif hasattr(rule, "activity_a") and hasattr(rule, "activity_b"):
            if rule.activity_a in acts and rule.activity_b in acts:
                filtered.append(rule)
    return filtered


def __event_based_log_repair(
    log,
    unsat_rules: List[AbstractRule],
):
    repaired_log = log
    for i in range(len(unsat_rules)):
        rule = unsat_rules[i]
        new_log = rule.repair(repaired_log)
        if not new_log:
            return None
        repaired_log = new_log
    # Just to make sure that we make progress
    # We remove empty traces that violate Existence, Init, or End
    if any(
        isinstance(r, (ExistenceRule, InitializationRule, EndRule)) for r in unsat_rules
    ):
        repaired_log = [trace for trace in repaired_log if len(trace) > 0]

    return repaired_log


def event_level_repair(
    log,
    unsat_rules: List[AbstractRule],
    im_function: Callable,
    original_rules: List[AbstractRule],
):
    original_event_count = sum(len(trace) for trace in log)
    num_traces_orig = len(log)
    repaired_log = __event_based_log_repair(log, unsat_rules)

    if not repaired_log:
        # repair failed
        return None

    new_rules = supported_rules(repaired_log, original_rules)

    repaired_event_count = sum(len(trace) for trace in repaired_log)
    if (
        repaired_event_count == original_event_count
        and len(repaired_log) == num_traces_orig
        and len(new_rules) == len(original_rules)
    ):
        return None
    return im_function(
        repaired_log,
        new_rules,
        repair_mode=RepairVariant.EventLevel,
    )


def __trace_level_log_repair(
    log,
    unsat_rules: List[AbstractRule],
):
    intersection = log.copy()
    for i in range(len(unsat_rules)):
        rule = unsat_rules[i]
        intersection = rule.apply(intersection)
    return intersection


def trace_level_repair(
    log,
    unsat_rules: List[AbstractRule],
    im_function: Callable,
    original_rules: List[AbstractRule],
):
    intersection = __trace_level_log_repair(log, unsat_rules)
    new_rules = supported_rules(intersection, original_rules)

    if (
        len(intersection) == len(log) and len(original_rules) == len(new_rules)
    ) or intersection is None:
        # No progress, continue trying
        return None
    return im_function(
        intersection,
        new_rules,
        repair_mode=RepairVariant.TraceLevel,
    )


def repair_mechanism(
    log,
    unsat_rules: List[AbstractRule],
    im_function: Callable,
    original_rules: List[AbstractRule],
    repair_mode: RepairVariant = REPAIR_VARIANT,
):
    if repair_mode == RepairVariant.EventLevel:
        return event_level_repair(log, unsat_rules, im_function, original_rules)
    elif repair_mode == RepairVariant.TraceLevel:
        return trace_level_repair(log, unsat_rules, im_function, original_rules)
    else:
        raise Exception(f"Unknown repair mode: {repair_mode}")
