from collections import defaultdict
from typing import Callable, List, Optional, Set

import networkx as nx
from inductive_miner.cuts.exclusive import ExclusiveChoiceCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child, build_signed_cdg
from inductive_miner.im_utils import RepairVariant
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import (
    AbstractRule,
    ExistenceRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    ResponseRule,
)

ARTIFICIAL_NONE_NODE = "ArtificialNoneNode"


def normalize_not_succession_pairs(
    rules: List[AbstractRule],
) -> List[AbstractRule]:
    rules = list(rules or [])

    not_succession_pairs = {
        (r.activity_a, r.activity_b) for r in rules if isinstance(r, NotSuccessionRule)
    }

    symmetric_pairs = {
        tuple(sorted((a, b)))
        for a, b in not_succession_pairs
        if (b, a) in not_succession_pairs
    }

    normalized_rules = [
        r
        for r in rules
        if not (
            isinstance(r, NotSuccessionRule)
            and tuple(sorted((r.activity_a, r.activity_b))) in symmetric_pairs
        )
    ]

    existing_not_coexistence = {
        tuple(sorted((r.activity_a, r.activity_b)))
        for r in normalized_rules
        if isinstance(r, NotCoExistenceRule)
    }

    for a, b in symmetric_pairs:
        if (a, b) not in existing_not_coexistence:
            normalized_rules.append(NotCoExistenceRule(a, b))

    return normalized_rules


def forced_by_existence(
    rules: List[AbstractRule],
) -> Optional[str]:
    existing = {
        rule.target_activity for rule in rules if isinstance(rule, ExistenceRule)
    }

    for rule in rules:
        if not isinstance(rule, NotCoExistenceRule):
            continue

        a = rule.activity_a
        b = rule.activity_b

        if a in existing and b not in existing:
            return a

        if b in existing and a not in existing:
            return b

    return None


def detect_groups(
    positive_graph: nx.DiGraph, negative_graph: nx.DiGraph
) -> List[Set[str]]:
    """
    Detect groups of activities that are connected by positive edges and not separated
    by negative edges. This is a heuristic based on coloring graph
    """
    positive_components = list(nx.weakly_connected_components(positive_graph))
    coloring = {}
    for i in range(len(positive_components)):
        for node in positive_components[i]:
            coloring[node] = i
    component_negative_graph = nx.Graph()
    component_negative_graph.add_nodes_from(range(len(positive_components)))
    for u, v in negative_graph.edges:
        component_u = coloring.get(u)
        component_v = coloring.get(v)
        if component_u is None or component_v is None:
            raise ValueError(
                f"Negative edge between {u} and {v} cannot be processed because one of the nodes is not in the positive graph"
            )
        if component_u == component_v:
            raise ValueError(
                f"Conflict between positive and negative rules for activities {u} and {v}"
            )
        component_negative_graph.add_edge(component_u, component_v)
    # Now, we will cover the component_negative_graph
    coloring = nx.coloring.greedy_color(
        component_negative_graph, strategy="largest_first"
    )
    color_to_group: dict[int, set[str]] = defaultdict(set)
    for component, color in coloring.items():
        color_to_group[color].update(positive_components[component])
    return list(color_to_group.values())


def project(log: List[List[str]], groups: List[Set[str]]) -> List[List[List[str]]]:
    projected_logs: List[List[List[str]]] = []

    for group in groups:
        activities = set(group)

        projected_log: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()

        for trace in log:
            projected_trace_tuple = tuple(
                activity for activity in trace if activity in activities
            )

            if projected_trace_tuple in seen:
                continue

            seen.add(projected_trace_tuple)
            projected_log.append(list(projected_trace_tuple))

        projected_logs.append(projected_log)

    return projected_logs


def apply(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    repair_mode=RepairVariant.TraceLevel,
    noise_threshold: float = 0,
    **kwargs,
) -> Optional[ProcessTree]:
    alphabet = set(dfg.nodes) - {ARTIFICIAL_NONE_NODE}
    rules = normalize_not_succession_pairs(rules)

    if not any(isinstance(r, NotCoExistenceRule) for r in rules or []):
        # inapplicable
        return None
    # --- EXISTENCE AND NOTCOEXISTENCE RULES CHECK ---
    forced_activity = forced_by_existence(rules)

    if forced_activity is not None:
        projected_log = [
            [event for event in trace if event == forced_activity] for trace in log
        ]

        projected_rules = [
            rule
            for rule in rules
            if (
                isinstance(rule, ExistenceRule)
                and rule.target_activity == forced_activity
            )
        ]

        return im_function(
            projected_log,
            projected_rules,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )

    positive_graph, negative_graph = build_signed_cdg(rules, alphabet)
    groups = detect_groups(positive_graph, negative_graph)
    if len(groups) <= 1:
        # inapplicable
        return None
    projected_logs = project(log, groups)
    projected_rules = ExclusiveChoiceCut.project_rules(rules, groups)
    tree = ProcessTree(operator=Operator.XOR)
    for projected_log, child_rules in zip(projected_logs, projected_rules):
        child = im_function(
            projected_log,
            child_rules,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )
        if child is None:
            return None
        add_child(tree, child)
    return tree


if __name__ == "__main__":
    rules = [
        NotSuccessionRule("A", "B"),
        NotSuccessionRule("B", "A"),
        ResponseRule("B", "D"),
        NotCoExistenceRule("C", "D"),
    ]
    rules = normalize_not_succession_pairs(rules)
    alphabet = {"A", "B", "C", "D"}
    positive_graph, negative_graph = build_signed_cdg(rules, alphabet)
    print(
        "Positive graph edges:", positive_graph.edges, "nodes: ", positive_graph.nodes
    )
    print(
        "Negative graph edges:", negative_graph.edges, "nodes: ", negative_graph.nodes
    )
    groups = detect_groups(positive_graph, negative_graph)
    print(groups)
