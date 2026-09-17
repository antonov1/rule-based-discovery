import time
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import networkx as nx
from automata.fa.dfa import DFA
from inductive_miner.cuts import LoopCut
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import (
    AbstractRule,
    AtMostOnceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
)
from rules.rule_utils import product_automaton


class RepairVariant(Enum):
    EventLevel = "event_level"
    TraceLevel = "trace_level"
    EditDistance = "edit_distance"
    Naive = "naive"


@dataclass
class Decomposition:
    operator: Operator
    sublogs: List[List[List[str]]]
    projected_rules: Optional[List[List[AbstractRule]]] = None


REPAIR_VARIANT = RepairVariant.EditDistance


def log_signature(log):
    return Counter(tuple(trace) for trace in log)


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
            if r.activity_a not in acts and r.activity_b not in acts:
                bad.append((str(r), acts))

    if bad:
        raise Exception(
            f"[{where}] unsupported rules: {bad} for acts={acts} and log_head={log[:5]}"
        )


def is_tau(node: ProcessTree) -> bool:
    return (
        node is not None
        and node.operator is None
        and node.label is None
        and not getattr(node, "children", None)
    )


def normalize_tree(node: ProcessTree):
    if node is None:
        return None

    if not getattr(node, "children", None):
        return node

    associative_ops = {
        Operator.SEQUENCE,
        Operator.XOR,
        Operator.PARALLEL,
    }

    normalized_children = []

    for child in node.children:
        child = normalize_tree(child)

        if child is None:
            continue

        if node.operator == Operator.SEQUENCE and is_tau(child):
            continue

        if node.operator in associative_ops and child.operator == node.operator:
            for grandchild in child.children:
                grandchild.parent = node
                normalized_children.append(grandchild)
        else:
            child.parent = node
            normalized_children.append(child)

    # XOR(tau, tau, ...) -> XOR(tau, ...)
    if node.operator == Operator.XOR:
        seen_tau = False
        deduplicated = []

        for child in normalized_children:
            if is_tau(child):
                if seen_tau:
                    continue
                seen_tau = True

            deduplicated.append(child)

        normalized_children = deduplicated

    node.children = normalized_children

    if node.operator in {Operator.XOR, Operator.LOOP}:
        if not node.children or all(is_tau(child) for child in node.children):
            tau = ProcessTree()
            tau.parent = node.parent
            return tau

    if node.operator == Operator.SEQUENCE and not node.children:
        tau = ProcessTree()
        tau.parent = node.parent
        return tau

    if node.operator in associative_ops and len(node.children) == 1:
        child = node.children[0]
        child.parent = node.parent
        return child

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
    rules: List[AbstractRule] = None,
    **kwargs,
):
    nodes = set(dfg_graph.nodes)
    rules = rules or []
    if not nodes:
        required_activities = {
            rule.target_activity
            for rule in rules
            if isinstance(
                rule,
                (
                    ExistenceRule,
                    InitializationRule,
                    EndRule,
                ),
            )
        }

        if len(required_activities) == 1:
            activity = next(iter(required_activities))
            return ProcessTree(label=activity)

        if len(required_activities) > 1:
            return {
                rule
                for rule in rules
                if isinstance(
                    rule,
                    (
                        ExistenceRule,
                        InitializationRule,
                        EndRule,
                    ),
                )
            }

        return process_tree

    if len(nodes) == 1 or (len(nodes) == 2 and "ArtificialNoneNode" in nodes):
        tree = _build_single_activity_tree(
            log,
            dfg_graph,
            nodes,
            rules,
            **kwargs,
        )

        return tree if tree is not None else process_tree

    raise Exception(
        "Base case error: log has multiple activities but no cut was found. "
        f"Log is: {log}, process_tree is: {process_tree}, "
        f"dfg_graph is: {dfg_graph}, nodes are: {nodes}"
    )


def _build_single_activity_tree(log, dfg_graph, nodes, rules, **kwargs) -> ProcessTree:
    nodes = nodes - {"ArtificialNoneNode"}
    if not nodes:
        return ProcessTree()  # Tau

    activity = nodes.pop()
    at_most_once = any(
        isinstance(rule, AtMostOnceRule) and rule.target_activity == activity
        for rule in rules
    )

    existence = any(
        isinstance(rule, (ExistenceRule, EndRule, InitializationRule))
        and rule.target_activity == activity
        for rule in rules
    )

    if at_most_once:
        if existence:
            return ProcessTree(label=activity)

        root = ProcessTree(operator=Operator.XOR)
        tau = ProcessTree()
        event = ProcessTree(label=activity)
        tau.parent = root
        event.parent = root
        root.children = [tau, event]
        return root
    if not dfg_graph.has_edge(activity, activity):
        unsat_rules = []
        for r in rules:
            if hasattr(r, "target_activity"):
                target = r.target_activity
                if target != activity:
                    unsat_rules.append(r)

        if unsat_rules:
            return set(unsat_rules)
        else:
            return ProcessTree(label=activity)

    has_empty_trace = [] in log
    if has_empty_trace and rules:
        group_0 = set()
        group_1 = {activity}
        unsat_rules = LoopCut.check_rules(rules, [group_0, group_1])

        if unsat_rules:
            return unsat_rules

        return _build_loop_tree(do_first=None, redo=activity)
    elif rules:
        group_0 = {activity}
        group_1 = set()
        unsat_rules = LoopCut.check_rules(rules, [group_0, group_1])

        if unsat_rules:
            return unsat_rules

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


def supported_rules_alphabet(alphabet, rules):
    if not rules:
        return []

    filtered = []

    for rule in rules:
        if hasattr(rule, "target_activity"):
            if rule.target_activity in alphabet:
                filtered.append(rule)
        elif hasattr(rule, "activity_a") and hasattr(rule, "activity_b"):
            if rule.activity_a in alphabet and rule.activity_b in alphabet:
                filtered.append(rule)
    return filtered


def supported_rules(log, rules):
    if not rules:
        return []

    acts = {a for trace in log for a in trace}
    filtered = []

    for rule in rules:
        if hasattr(rule, "target_activity"):
            if rule.target_activity in acts:
                filtered.append(rule)
        elif hasattr(rule, "activity_a"):
            if rule.activity_a in acts and rule.activity_b in acts:
                filtered.append(rule)
            elif rule.activity_a in acts or rule.activity_b in acts:
                if not isinstance(rule, (NotSuccessionRule, NotCoExistenceRule)):
                    filtered.append(rule)
    return filtered


def __event_based_log_repair(
    log,
    unsat_rules: List[AbstractRule],
):
    repaired_log = log
    for rule in unsat_rules:
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
    original_rules: List[AbstractRule],
):
    original_event_count = sum(len(trace) for trace in log)
    num_traces_orig = len(log)
    repaired_log = __event_based_log_repair(log, unsat_rules)

    new_rules = supported_rules(repaired_log, original_rules)

    repaired_event_count = sum(len(trace) for trace in repaired_log)
    if (
        repaired_event_count == original_event_count
        and len(repaired_log) == num_traces_orig
        and len(new_rules) == len(original_rules)
    ):
        return None
    return repaired_log, new_rules


def __trace_level_log_repair(
    log,
    unsat_rules: List[AbstractRule],
    original_rules: List[AbstractRule],
):
    intersection = log.copy()
    for rule in unsat_rules:
        intersection = rule.apply(intersection)
    new_rules = supported_rules(intersection, original_rules)
    return intersection, new_rules


def trace_level_repair(
    log,
    unsat_rules: List[AbstractRule],
    original_rules: List[AbstractRule],
):
    intersection, new_rules = __trace_level_log_repair(log, unsat_rules, original_rules)

    if (
        len(intersection) == len(log) and len(original_rules) == len(new_rules)
    ) or intersection is None:
        # No progress, continue trying
        return None
    return intersection, new_rules


def repair_mechanism(
    log: List[List[str]],
    unsat_rules: List[AbstractRule],
    original_rules: List[AbstractRule],
    repair_mode: RepairVariant = REPAIR_VARIANT,
):
    if repair_mode == RepairVariant.EventLevel:
        start = time.perf_counter()

        repair = event_level_repair(log, unsat_rules, original_rules)

        time.perf_counter() - start

        # with open("repair_timings_event_level.txt", "a") as f:
        #    f.write(f"{elapsed:.6f}, " f"{len(log)}, " f"{len(unsat_rules)}\n")
        return repair

    elif repair_mode == RepairVariant.TraceLevel:
        start = time.perf_counter()
        repair = trace_level_repair(log, unsat_rules, original_rules)
        time.perf_counter() - start
        # with open("repair_timings_trace_level.txt", "a") as f:
        #    f.write(f"{end:.6f}, " f"{len(log)}, " f"{len(unsat_rules)}\n")
        return repair
    elif repair_mode == RepairVariant.EditDistance:
        start = time.perf_counter()
        repair = apply_edit_distance_repair(
            log,
            original_rules,
            unsat_rules,
        )
        time.perf_counter() - start
        # with open("repair_timings_edit_distance.txt", "a") as f:
        #    f.write(f"{end:.6f}, " f"{len(log)}, " f"{len(unsat_rules)}\n")
        return repair
    elif repair_mode == RepairVariant.Naive:
        return None
    else:
        raise Exception(f"Unknown repair mode: {repair_mode}")


#### APPROXIMATE REPAIR MECHANISM BASED ON EDIT DISTANCE TO THE PRODUCT AUTOMATON OF THE RULES ####


class OperationsCost(Enum):
    Insert = 1
    Delete = 1
    Substitute = 2


def _to_edit_distance_graph(
    trace,
    automaton: DFA,
    allow_replace: bool = False,
    skip_useless_insert_self_loops: bool = True,
) -> nx.MultiDiGraph:
    G = (
        nx.MultiDiGraph()
    )  # We need a MultiDiGraph because multiple edges between the same nodes are possible
    n = len(trace)

    # Nodes encode (trace_position, automaton_state)
    for i in range(n + 1):
        for state in automaton.states:
            G.add_node((i, state))

    for i in range(n + 1):
        for state in automaton.states:

            # Keep / delete / replace are only possible if there is still
            # an observed event to consume
            if i < n:
                observed = trace[i]

                # Keep, cost is 0
                q_next = automaton.transitions[state].get(observed)
                if q_next is not None:
                    G.add_edge(
                        (i, state),
                        (i + 1, q_next),
                        weight=0,
                        op="keep",
                        consume=observed,
                        output=observed,
                    )

                # Delete the event
                G.add_edge(
                    (i, state),
                    (i + 1, state),
                    weight=OperationsCost.Delete.value,
                    op="delete",
                    consume=observed,
                    output=None,
                )

                # Replace the event
                if allow_replace:
                    for replacement in automaton.input_symbols:
                        if replacement == observed:
                            continue

                        q_next = automaton.transitions[state].get(replacement)
                        if q_next is not None:
                            G.add_edge(
                                (i, state),
                                (i + 1, q_next),
                                weight=OperationsCost.Substitute.value,
                                op="replace",
                                consume=observed,
                                output=replacement,
                            )

            # Insert an event
            # we might need additional events at the end to reach acceptance
            for inserted in automaton.input_symbols:
                q_next = automaton.transitions[state].get(inserted)
                if q_next is None:
                    continue

                if skip_useless_insert_self_loops and q_next == state:
                    continue

                G.add_edge(
                    (i, state),
                    (i, q_next),
                    weight=OperationsCost.Insert.value,
                    op="insert",
                    consume=None,
                    output=inserted,
                )

    return G


def _best_edge_data(G: nx.MultiDiGraph, u, v):
    """
    Pick the minimum-weight edge between u and v for MultiGraph G, and return its data
    """
    edge_options = G.get_edge_data(u, v)

    if edge_options is None:
        raise RuntimeError(f"No edge between {u} and {v}")

    return min(
        edge_options.values(),
        key=lambda data: data.get("weight", 1),
    )


def repair_trace(trace, automaton: DFA):
    G = _to_edit_distance_graph(trace, automaton)

    source = (0, automaton.initial_state)

    best_cost = float("inf")
    best_path = None

    for final_state in automaton.final_states:
        target = (len(trace), final_state)

        try:
            cost = nx.shortest_path_length(
                G,
                source=source,
                target=target,
                weight="weight",
            )
            path = nx.shortest_path(
                G,
                source=source,
                target=target,
                weight="weight",
            )
        except nx.NetworkXNoPath:
            continue

        if cost < best_cost:
            best_cost = cost
            best_path = path

    if best_path is None:
        return None

    edits = []
    repaired = []

    for u, v in zip(best_path, best_path[1:]):
        data = _best_edge_data(G, u, v)

        edits.append(
            {
                "from": u,
                "to": v,
                "op": data["op"],
                "consume": data["consume"],
                "output": data["output"],
                "cost": data["weight"],
            }
        )

        if data["output"] is not None:
            repaired.append(data["output"])
    return {
        "cost": best_cost,
        "path": best_path,
        "edits": edits,
        "repaired_trace": repaired,
    }


def apply_edit_distance_repair(
    log,
    rules: List[AbstractRule],
    unsat_rules: List[AbstractRule],
):
    # Find the traces that are not accepted by the product automaton
    original_log = [list(trace) for trace in log]
    alphabet = set(e for trace in log for e in trace)
    for rule in rules or []:
        if hasattr(rule, "activity_a"):
            alphabet.add(rule.activity_a)
        if hasattr(rule, "activity_b"):
            alphabet.add(rule.activity_b)
        if hasattr(rule, "target_activity"):
            alphabet.add(rule.target_activity)
    automata_by_rule = {r: r.to_automaton(alphabet=set(alphabet)) for r in rules}
    product = product_automaton(rules, alphabet, automata_by_rule)
    if not len(product.final_states):
        raise Exception(
            f"Product automaton is empty, cannot apply edit distance repair. Automaton: {product}"
        )
    # We filter out satisfied traces first to avoid unnecessary repair attempts
    for rule in unsat_rules:
        log = rule.repair(log)

    unsat_traces = [trace for trace in original_log if trace not in log]
    for trace in unsat_traces:
        repair_result = repair_trace(trace, product)
        log.append(repair_result["repaired_trace"])
    # Check if we made any progress, e.g., decreased log size or number of events
    if log_signature(log) == log_signature(original_log):
        return None
    new_rules = supported_rules(log, rules)
    return log, new_rules


def problem_signature(log, rules):
    return (
        tuple(sorted(tuple(trace) for trace in log)),
        tuple(sorted(str(rule) for rule in (rules or []))),
    )


if __name__ == "__main__":
    from automata.fa.dfa import DFA

    dfa = DFA(
        states={"q0", "q1", "q2"},
        input_symbols={"a", "b"},
        transitions={
            "q0": {
                "a": "q1",
                "b": "q0",
            },
            "q1": {
                "a": "q1",
                "b": "q2",
            },
            "q2": {
                "a": "q2",
                "b": "q2",
            },
        },
        initial_state="q0",
        final_states={"q2"},
    )
    trace = ["c", "c", "d", "b"]
    result = repair_trace(trace, dfa)
    print(result)
