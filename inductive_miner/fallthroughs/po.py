from dataclasses import dataclass
from typing import Callable, List, Optional, Set, Tuple

import networkx as nx
from inductive_miner.cuts.sequence import SequenceCut
from inductive_miner.fallthroughs.fallthrough_utils import (
    add_child,
    ARTIFICIAL_END,
    ARTIFICIAL_START,
    build_cdg,
)
from inductive_miner.im_utils import RepairVariant, supported_rules_alphabet
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    NotCoExistenceRule,
)
from utils.directly_follows_graph import DirectlyFollowsGraph

ARTIFICIAL_NONE_NODE = "ArtificialNoneNode"


def abstract_dfg(
    dfg: nx.DiGraph,
    components: List[Set[str]],
) -> nx.DiGraph:
    """
    Abstract an activity-level DFG into a component-level DFG.

    Original DFG format:
      - normal edges: a -> b with edge attribute weight
      - start counts: dfg.nodes[a]["start"]
      - end counts: dfg.nodes[a]["end"]
      - empty traces: ArtificialNoneNode self-loop

    Abstracted DFG format:
      - nodes are component indices: 0, 1, ...
      - start/end counts are summed onto component nodes
      - edge weights are summed between component indices
      - ArtificialNoneNode is preserved if present
    """
    new_dfg = nx.DiGraph()
    new_dfg.add_nodes_from(range(len(components)))

    component_of = {}

    for i, component in enumerate(components):
        for activity in component:
            component_of[activity] = i

    # Aggregate node-level start & end weights
    for activity, data in dfg.nodes(data=True):
        if activity == ARTIFICIAL_NONE_NODE:
            # skip it
            continue

        if activity not in component_of:
            continue

        component = component_of[activity]

        start_count = data.get("start", 0)
        end_count = data.get("end", 0)

        if start_count:
            new_dfg.nodes[component]["start"] = (
                new_dfg.nodes[component].get("start", 0) + start_count
            )

        if end_count:
            new_dfg.nodes[component]["end"] = (
                new_dfg.nodes[component].get("end", 0) + end_count
            )

    # Aggregate edge weights
    for source, target, data in dfg.edges(data=True):
        # Empty-trace are ignored in this case
        if source == ARTIFICIAL_NONE_NODE and target == ARTIFICIAL_NONE_NODE:
            continue
        if source not in component_of or target not in component_of:
            continue

        source_component = component_of[source]
        target_component = component_of[target]

        weight = data.get("weight", 1)

        if source_component == target_component:
            continue

        if new_dfg.has_edge(source_component, target_component):
            new_dfg[source_component][target_component]["weight"] += weight
        else:
            new_dfg.add_edge(
                source_component,
                target_component,
                weight=weight,
            )

    return new_dfg


@dataclass(frozen=True)
class RuleBasedPO:
    groups: List[Set[str]]
    edges: Set[Tuple[int, int]]


def get_chain_components(
    rules: List[AbstractRule],
    alphabet: Set[str],
) -> List[Set[str]]:
    chain_graph = nx.Graph()
    chain_graph.add_nodes_from(alphabet)

    for rule in rules or []:
        if isinstance(rule, (ChainPrecedenceRule, ChainResponseRule)):
            if rule.activity_a in alphabet and rule.activity_b in alphabet:
                chain_graph.add_edge(rule.activity_a, rule.activity_b)

    return [set(component) for component in nx.connected_components(chain_graph)]


def merge_components_by_not_coexistence(
    components: List[Set[str]],
    rules: List[AbstractRule],
) -> List[Set[str]]:
    """
    Keep activities connected by NotCoExistence in the same PO branch.

    This does not model XOR by itself. It only prevents the PO fall-through
    from treating the two activities as unrelated parallel branches.
    """
    component_of = {}

    for i, component in enumerate(components):
        for activity in component:
            component_of[activity] = i

    merge_graph = nx.Graph()
    merge_graph.add_nodes_from(range(len(components)))

    for rule in rules or []:
        if not isinstance(rule, NotCoExistenceRule):
            continue

        a = rule.activity_a
        b = rule.activity_b

        if a not in component_of or b not in component_of:
            continue

        ca = component_of[a]
        cb = component_of[b]

        if ca != cb:
            merge_graph.add_edge(ca, cb)

    merged_components = []

    for component_ids in nx.connected_components(merge_graph):
        merged = set().union(*(components[i] for i in component_ids))
        merged_components.append(merged)

    return merged_components


def merge_groups_connected_by_chain_rules(
    groups: List[Set[str]],
    rules: List[AbstractRule],
) -> List[Set[str]]:
    """
    If a chain rule still connects activities in different sequence layers,
    merge the entire interval between them.

    This avoids producing A -> something -> B for ChainResponse(A, B) or
    ChainPrecedence(A, B).
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
            if high - low == 1:
                # they are already consecutive
                continue
            merged_group = set().union(*groups[low : high + 1])

            groups = groups[:low] + [merged_group] + groups[high + 1 :]
            changed = True
            break

    return groups


def calculate_weight(dfg, source, target) -> float:
    """
    Runs Dijkstra, treates DFG weights as inverses
    """
    if source == target:
        return 0
    if source not in dfg.nodes or target not in dfg.nodes:
        return 0
    cost_graph = nx.DiGraph()
    cost_graph.add_nodes_from(dfg.nodes)
    for a, b, data in dfg.edges(data=True):
        if a == b:
            continue
        weight = data.get("weight", 1)
        if weight <= 0:
            continue
        cost_graph.add_edge(a, b, cost=1 / weight)
    try:
        path = nx.dijkstra_path(cost_graph, source, target, weight="cost")
    except nx.NetworkXNoPath:
        return 0
    total_weight = 0
    for a, b in zip(path, path[1:]):
        total_weight += dfg[a][b].get("weight", 1)
    return total_weight


def handle_chain_components(
    po: RuleBasedPO, rules: Set[AbstractRule], dfg: nx.DiGraph
) -> Optional[RuleBasedPO]:
    components_with_chain_rules = set()
    for r in rules:
        if isinstance(r, ChainPrecedenceRule) or isinstance(r, ChainResponseRule):
            act_a, act_b = r.activity_a, r.activity_b
            for i, group in enumerate(po.groups):
                if act_a in group or act_b in group:
                    components_with_chain_rules.add(i)
    if not components_with_chain_rules:
        return po
    # build the graph of components
    g = nx.DiGraph()
    g.add_nodes_from(range(len(po.groups)))
    g.add_edges_from(po.edges)

    if not nx.is_directed_acyclic_graph(g):
        return None

    closure = nx.transitive_closure_dag(g)
    abstracted_dfg = abstract_dfg(dfg, po.groups)

    def comparable(i: int, j: int) -> bool:
        return i == j or closure.has_edge(i, j) or closure.has_edge(j, i)

    new_edges = po.edges
    for cmp in components_with_chain_rules:
        for other_cmp in g.nodes:
            if other_cmp == cmp:
                continue
            if not comparable(cmp, other_cmp):
                # those are parallel
                cost_cmp_o = calculate_weight(abstracted_dfg, cmp, other_cmp)
                cost_o_cmp = calculate_weight(abstracted_dfg, other_cmp, cmp)
                (
                    new_edges.add((other_cmp, cmp))
                    if cost_o_cmp > cost_cmp_o
                    else new_edges.add((cmp, other_cmp))
                )
                print(f"New edges: {new_edges}")
    po.edges.update(new_edges)
    return po


def detect_rule_based_po(
    rules: List[AbstractRule], alphabet: Set[str], dfg: nx.DiGraph
) -> Optional[RuleBasedPO]:
    """
    Detect a rule-induced partial order between activity blocks.

    This does not directly perform layering. It returns:
        groups = block activities
        edges = partial-order edges between block indices
    """
    if not alphabet:
        return None

    rules = rules or []

    cdg = build_cdg(rules, alphabet)

    print(
        f"Constructed CDG with edges: {list(cdg.edges)} "
        f"and nodes: {list(cdg.nodes)}"
    )

    activity_graph = cdg.subgraph(alphabet).copy()

    start_nodes = {
        activity for activity in alphabet if cdg.has_edge(ARTIFICIAL_START, activity)
    }

    end_nodes = {
        activity for activity in alphabet if cdg.has_edge(activity, ARTIFICIAL_END)
    }

    if start_nodes & end_nodes:
        return None
    # We require a PO to have at most one start and one end node. Otherwise, it is unsatisfiable because Init(A) and Init(B) cannot hold together.
    if len(start_nodes) > 1 or len(end_nodes) > 1:
        return None

    if activity_graph.number_of_edges() == 0 and not start_nodes and not end_nodes:
        return None

    if not nx.is_directed_acyclic_graph(activity_graph):
        return None

    components = get_chain_components(rules, alphabet)
    components = merge_components_by_not_coexistence(components, rules)

    print(
        "Components after merging by chain rules and not co-existence: " f"{components}"
    )

    component_of = {}

    for i, component in enumerate(components):
        for activity in component:
            component_of[activity] = i

    block_graph = nx.DiGraph()
    block_graph.add_nodes_from(range(len(components)))

    for source, target in activity_graph.edges:
        source_component = component_of[source]
        target_component = component_of[target]

        if source_component != target_component:
            block_graph.add_edge(source_component, target_component)

    start_components = {
        component_of[activity] for activity in start_nodes if activity in component_of
    }

    end_components = {
        component_of[activity] for activity in end_nodes if activity in component_of
    }

    if start_components & end_components:
        return None

    # Initialization/End as weak global ordering constraints.
    #
    # If Initialization(A), then A's block should be before all other blocks
    # unless this creates a cycle.
    for start_component in start_components:
        for other in block_graph.nodes:
            if other != start_component:
                block_graph.add_edge(start_component, other)

    # If End(F), then all other blocks should be before F's block unless
    # this creates a cycle.
    for end_component in end_components:
        for other in block_graph.nodes:
            if other != end_component:
                block_graph.add_edge(other, end_component)

    if not nx.is_directed_acyclic_graph(block_graph):
        return None

    # If there is more than one component and no block-level edges, this is still
    # a valid partial order: all components are unordered/parallel.
    if block_graph.number_of_nodes() == 0:
        return None

    po = RuleBasedPO(
        groups=components,
        edges=set(block_graph.edges),
    )

    po = handle_chain_components(po, rules, dfg)

    if po is None:
        return None

    po_graph = nx.DiGraph()
    po_graph.add_nodes_from(range(len(po.groups)))
    po_graph.add_edges_from(po.edges)

    if not nx.is_directed_acyclic_graph(po_graph):
        return None

    if po_graph.number_of_edges() == 0:
        return po

    try:
        reduced_graph = nx.transitive_reduction(po_graph)
    except nx.NetworkXError:
        return None

    return RuleBasedPO(
        groups=po.groups,
        edges=set(reduced_graph.edges),
    )


def topological_layers_for_nodes(
    graph: nx.DiGraph,
    nodes: Set[int],
) -> Optional[List[Set[int]]]:
    remaining = set(nodes)
    layers: List[Set[int]] = []

    while remaining:
        layer = {
            node
            for node in remaining
            if all(
                predecessor not in remaining for predecessor in graph.predecessors(node)
            )
        }

        if not layer:
            return None

        layers.append(layer)
        remaining -= layer

    return layers


def split_group_by_chain_rules(
    group: Set[str],
    rules: List[AbstractRule],
) -> List[Set[str]]:
    if len(group) <= 1:
        return [set(group)]

    graph = nx.DiGraph()
    graph.add_nodes_from(group)

    for rule in rules or []:
        if isinstance(rule, (ChainResponseRule, ChainPrecedenceRule)):
            if rule.activity_a in group and rule.activity_b in group:
                graph.add_edge(rule.activity_a, rule.activity_b)

    if graph.number_of_edges() == 0:
        return [set(group)]

    if not nx.is_directed_acyclic_graph(graph):
        return [set(group)]

    return [set(layer) for layer in nx.topological_generations(graph) if layer]


def po_to_parallel_sequence_branches(
    po: RuleBasedPO,
    rules: List[AbstractRule],
) -> Optional[List[List[Set[str]]]]:
    graph = nx.DiGraph()
    graph.add_nodes_from(range(len(po.groups)))
    graph.add_edges_from(po.edges)

    if not nx.is_directed_acyclic_graph(graph):
        return None

    branches: List[List[Set[str]]] = []

    for weak_nodes in nx.connected_components(graph.to_undirected()):
        weak_nodes = set(weak_nodes)

        local_layers = topological_layers_for_nodes(graph, weak_nodes)

        if local_layers is None:
            return None

        branch = []

        for layer in local_layers:
            layer_group = set().union(*(po.groups[i] for i in layer))

            split_layers = split_group_by_chain_rules(
                layer_group,
                rules,
            )

            branch.extend(split_layers)

        branch_alphabet = set().union(*branch)
        branch_rules = supported_rules_alphabet(rules, branch_alphabet)

        branch = merge_groups_connected_by_chain_rules(branch, branch_rules)

        if branch:
            branches.append(branch)

    if not branches:
        return None

    # Now this is checked AFTER internal chain splitting.
    if len(branches) == 1 and len(branches[0]) <= 1:
        return None

    print(f"Detected PO branches: {branches}")

    return branches


def mine_sequence_branch(
    im_function: Callable,
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule],
    groups: List[Set[str]],
    repair_mode,
    noise_threshold: float,
) -> Optional[ProcessTree]:
    if not groups:
        return None

    branch_alphabet = set().union(*groups)
    branch_rules = supported_rules_alphabet(branch_alphabet, rules)

    violations = SequenceCut.check_rules(branch_rules, groups)

    if violations:
        return None

    projections = SequenceCut(dfg).relaxed_projection(log, groups)
    projected_rules = SequenceCut.project_rules(branch_rules, groups)

    if len(projections) != len(groups):
        return None

    # One group in this branch: just mine the projected child.
    if len(groups) == 1:
        child_rules = projected_rules[0] if projected_rules else []

        child = im_function(
            projections[0],
            child_rules or [],
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )

        return child

    parent = ProcessTree(operator=Operator.SEQUENCE)

    for i, projected_log in enumerate(projections):
        child_rules = projected_rules[i] if projected_rules else []

        child = im_function(
            projected_log,
            child_rules or [],
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )

        if child is None:
            return None

        add_child(parent, child)

    return parent


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

    po = detect_rule_based_po(rules, alphabet, dfg)
    print(f"Detected po is: {po}")

    if po is None:
        return None

    branches = po_to_parallel_sequence_branches(po, rules)

    if branches is None:
        return None

    branch_trees = []

    for branch_groups in branches:
        branch_tree = mine_sequence_branch(
            im_function=im_function,
            log=log,
            dfg=dfg,
            rules=rules,
            groups=branch_groups,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )

        if branch_tree is None:
            return None

        branch_trees.append(branch_tree)

    if not branch_trees:
        return None
    if len(branch_trees) == 1 and len(po.groups) == 1:
        return None
    if len(branch_trees) == 1:
        return branch_trees[0]

    parent = ProcessTree(operator=Operator.PARALLEL)

    for branch_tree in branch_trees:
        add_child(parent, branch_tree)

    return parent


if __name__ == "__main__":
    from rules import ChainResponseRule, ExistenceRule
    from utils.directly_follows_graph import DirectlyFollowsGraph

    rules = [
        ExistenceRule("m"),
        ChainResponseRule("m", "r"),
        ExistenceRule("r"),
    ]

    # Concrete minimized version of the data
    # many traces are ["m", "r"], with one trace ["r", "m", "r"].
    log = (
        [["m", "r"] for _ in range(20)]
        + [["r", "m", "r"]]
        + [["m", "r"] for _ in range(20)]
    )

    alphabet = {"m", "r"}

    dfg = DirectlyFollowsGraph(log).graph

    print("DFG nodes:")
    print(list(dfg.nodes(data=True)))

    print("DFG edges:")
    print(list(dfg.edges(data=True)))

    po = detect_rule_based_po(rules, alphabet, dfg)
    print("Detected PO:")
    print(po)

    if po is not None:
        branches = po_to_parallel_sequence_branches(po, rules)
        print("Branches:")
        print(branches)
    else:
        print("PO fall-through did not fire.")
