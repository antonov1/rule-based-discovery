from typing import Callable, List, Optional, Set

import networkx as nx
from inductive_miner.cuts.sequence import SequenceCut
from inductive_miner.fallthroughs.fallthrough_utils import (
    add_child,
    ARTIFICIAL_END,
    ARTIFICIAL_START,
    build_cdg,
)
from inductive_miner.im_utils import RepairVariant
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    NotCoExistenceRule,
)

ARTIFICIAL_NONE_NODE = "ArtificialNoneNode"


def get_chain_components(
    rules: List[AbstractRule],
    alphabet: Set[str],
) -> List[Set[str]]:
    """
    Activities connected by chain rules are treated as indivisible components.

    This prevents a ChainPrecedence/ChainResponse pair from being split across
    different recursive children, which can destroy adjacency semantics.
    """
    chain_graph = nx.Graph()
    chain_graph.add_nodes_from(alphabet)

    for rule in rules or []:
        if isinstance(rule, (ChainPrecedenceRule, ChainResponseRule)):
            if rule.activity_a in alphabet and rule.activity_b in alphabet:
                chain_graph.add_edge(rule.activity_a, rule.activity_b)

    return [set(component) for component in nx.connected_components(chain_graph)]


def merge_groups_connected_by_chain_rules(
    groups: List[Set[str]],
    rules: List[AbstractRule],
) -> List[Set[str]]:
    """
    If a chain rule still connects activities in different groups, merge the
    whole interval between those groups. This avoids producing:

        A -> something -> B

    for a chain rule A -> B.
    """
    rules = rules or []
    groups = [set(group) for group in groups]

    changed = True

    while changed:
        changed = False

        position = {}
        for i, group in enumerate(groups):
            for activity in group:
                position[activity] = i

        for rule in rules:
            if not isinstance(rule, (ChainPrecedenceRule, ChainResponseRule)):
                continue

            a = rule.activity_a
            b = rule.activity_b

            if a not in position or b not in position:
                continue

            i = position[a]
            j = position[b]

            if i == j:
                continue

            low, high = sorted((i, j))
            merged_group = set().union(*groups[low:high])
            high += 1
            # Just take the entire branch together
            groups = groups[:low] + [merged_group] + groups[high:]
            changed = True
            break

    return groups


def merge_components_by_not_coexistence(
    components: List[Set[str]],
    rules: List[AbstractRule],
) -> List[Set[str]]:
    component_of = {}

    for i, component in enumerate(components):
        for activity in component:
            component_of[activity] = i

    merge_graph = nx.Graph()
    merge_graph.add_nodes_from(range(len(components)))

    for r in rules or []:
        if not isinstance(r, NotCoExistenceRule):
            continue

        a = r.activity_a
        b = r.activity_b

        if a not in component_of or b not in component_of:
            continue

        ca = component_of[a]
        cb = component_of[b]

        if ca != cb:
            merge_graph.add_edge(ca, cb)

    return [
        set().union(*(components[i] for i in component_ids))
        for component_ids in nx.connected_components(merge_graph)
    ]


def detect_groups(
    rules: List[AbstractRule],
    alphabet: Set[str],
) -> Optional[List[Set[str]]]:
    if not alphabet:
        return None

    rules = rules or []

    cdg = build_cdg(rules, alphabet)

    activity_graph = cdg.subgraph(alphabet).copy()

    start_nodes = {
        activity for activity in alphabet if cdg.has_edge(ARTIFICIAL_START, activity)
    }

    end_nodes = {
        activity for activity in alphabet if cdg.has_edge(activity, ARTIFICIAL_END)
    }

    if start_nodes & end_nodes:
        return None

    # Multiple start or end nodes do not make sense from DECLARE semantics perspective
    if len(start_nodes) > 1 or len(end_nodes) > 1:
        return None

    # No partial order identifiable
    if activity_graph.number_of_edges() == 0 and not start_nodes and not end_nodes:
        return None
    # PO should be a DAG
    if not nx.is_directed_acyclic_graph(activity_graph):
        return None

    components = get_chain_components(rules, alphabet)
    components = merge_components_by_not_coexistence(
        components,
        rules,
    )
    component_of = {}
    for i, component in enumerate(components):
        for activity in component:
            component_of[activity] = i

    component_graph = nx.DiGraph()
    component_graph.add_nodes_from(range(len(components)))

    for source, target in activity_graph.edges:
        source_component = component_of[source]
        target_component = component_of[target]

        if source_component != target_component:
            component_graph.add_edge(source_component, target_component)

    if not nx.is_directed_acyclic_graph(component_graph):
        return None

    start_components = {component_of[activity] for activity in start_nodes}
    end_components = {component_of[activity] for activity in end_nodes}

    if start_components & end_components:
        return None

    groups: List[Set[str]] = []

    remaining = set(component_graph.nodes) - start_components - end_components

    while remaining:
        layer_components = {
            component
            for component in remaining
            if all(
                predecessor not in remaining
                for predecessor in component_graph.predecessors(component)
            )
        }

        if not layer_components:
            return None

        layer = set().union(*(components[i] for i in layer_components))
        groups.append(layer)
        remaining -= layer_components

    if start_components:
        start_group = set().union(*(components[i] for i in start_components))
        groups = [start_group] + groups

    if end_components:
        end_group = set().union(*(components[i] for i in end_components))
        groups = groups + [end_group]

    groups = merge_groups_connected_by_chain_rules(groups, rules)

    if len(groups) <= 1:
        return None

    return groups


def apply(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    repair_mode=RepairVariant.TraceLevel,
    noise_threshold: float = 0,
    **kwargs,
) -> Optional[ProcessTree]:
    rules = rules or []

    if not rules:
        return None

    alphabet = set(dfg.nodes) - {ARTIFICIAL_NONE_NODE}

    groups = detect_groups(rules, alphabet)

    if groups is None:
        return None
    violations = SequenceCut.check_rules(rules, groups)
    if violations:
        return None

    projections = SequenceCut(dfg).relaxed_projection(log, groups)
    projected_rules = SequenceCut.project_rules(rules, groups)

    if len(projections) != len(groups):
        return None

    parent = ProcessTree(operator=Operator.SEQUENCE)

    for i, projected_log in enumerate(projections):
        child_rules = projected_rules[i] if projected_rules else None

        if child_rules:
            child = im_function(
                projected_log,
                child_rules,
                repair_mode=repair_mode,
                noise_threshold=noise_threshold,
            )
        else:
            child = im_function(
                projected_log,
                repair_mode=repair_mode,
                noise_threshold=noise_threshold,
            )
        sublog_acts = {e for trace in projected_log for e in trace}
        print(
            f"Child rules: {child_rules}, child tree: {child}, sublog activities: {sublog_acts}"
        )
        add_child(parent, child)

    return parent


if __name__ == "__main__":
    from rules import (
        ChainPrecedenceRule,
        ChainResponseRule,
        EndRule,
        InitializationRule,
        ResponseRule,
    )

    rules = [
        InitializationRule("A"),
        EndRule("F"),
        ResponseRule("A", "B"),
        ResponseRule("A", "C"),
        ChainPrecedenceRule("D", "E"),
        ChainResponseRule("D", "F"),
        NotCoExistenceRule("B", "E"),
    ]

    alphabet = {"A", "B", "C", "D", "E", "F"}

    groups = detect_groups(rules, alphabet)

    print(groups)
