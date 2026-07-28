from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import reduce
from itertools import combinations
from typing import Dict, List, Set, Tuple, TypeAlias

from automata.fa.dfa import DFA
from automata.fa.nfa import NFA
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)


@dataclass
class LogStats:
    trace_count: int = 0

    activity_occurrence_count: Counter = field(default_factory=Counter)
    activity_trace_count: Counter = field(default_factory=Counter)

    start_count: Counter = field(default_factory=Counter)
    end_count: Counter = field(default_factory=Counter)

    # Number of traces containing both A and B
    co_existence_count: Counter = field(default_factory=Counter)

    # AtMostOnce
    activity_at_most_once_valid: Counter = field(default_factory=Counter)

    # Number of traces satisfying each directed constraint
    responded_existence_valid: Counter = field(default_factory=Counter)
    response_valid: Counter = field(default_factory=Counter)
    precedence_valid: Counter = field(default_factory=Counter)
    chain_response_valid: Counter = field(default_factory=Counter)
    chain_precedence_valid: Counter = field(default_factory=Counter)
    not_succession_valid: Counter = field(default_factory=Counter)

    # Number of traces satisfying the constraint, including vacuous traces
    responded_existence_support_valid: Counter = field(default_factory=Counter)
    response_support_valid: Counter = field(default_factory=Counter)
    precedence_support_valid: Counter = field(default_factory=Counter)
    chain_response_support_valid: Counter = field(default_factory=Counter)
    chain_precedence_support_valid: Counter = field(default_factory=Counter)
    not_succession_support_valid: Counter = field(default_factory=Counter)


Activity: TypeAlias = Hashable
Trace: TypeAlias = Sequence[Activity]


def build_log_stats(log: Iterable[Trace]) -> tuple[LogStats, tuple[Activity, ...]]:
    traces = [tuple(trace) for trace in log]
    activities = tuple(sorted({activity for trace in traces for activity in trace}))

    stats = LogStats()

    for trace in traces:
        if not trace:
            continue

        stats.trace_count += 1
        stats.start_count[trace[0]] += 1
        stats.end_count[trace[-1]] += 1

        positions: dict[Activity, list[int]] = {}

        for index, activity in enumerate(trace):
            positions.setdefault(activity, []).append(index)
            stats.activity_occurrence_count[activity] += 1

        present = set(positions)

        for activity in present:
            stats.activity_trace_count[activity] += 1

        for a, b in combinations(present, 2):
            stats.co_existence_count[frozenset((a, b))] += 1

        for a in activities:
            if len(positions.get(a, [])) <= 1:
                stats.activity_at_most_once_valid[a] += 1
            a_present = a in positions

            for b in activities:
                if a == b:
                    continue

                b_present = b in positions
                key = (a, b)

                # RespondedExistence(a, b):
                # valid if A is absent, or both A and B occur
                responded_valid = not a_present or b_present
                if responded_valid:
                    stats.responded_existence_support_valid[key] += 1
                if a_present and b_present:
                    stats.responded_existence_valid[key] += 1

                # Response(a, b):
                # every A must have some later B
                response_valid = not a_present or (
                    b_present
                    and all(
                        any(b_pos > a_pos for b_pos in positions[b])
                        for a_pos in positions[a]
                    )
                )
                if response_valid:
                    stats.response_support_valid[key] += 1
                if a_present and response_valid:
                    stats.response_valid[key] += 1

                # Precedence(a, b):
                # every B must be preeceeded by an earlier A
                precedence_valid = not b_present or (
                    a_present
                    and all(
                        any(a_pos < b_pos for a_pos in positions[a])
                        for b_pos in positions[b]
                    )
                )
                if precedence_valid:
                    stats.precedence_support_valid[key] += 1
                if b_present and precedence_valid:
                    stats.precedence_valid[key] += 1

                # ChainResponse(a, b):
                # every A is immediately followed by B
                chain_response_valid = not a_present or all(
                    a_pos + 1 < len(trace) and trace[a_pos + 1] == b
                    for a_pos in positions[a]
                )
                if chain_response_valid:
                    stats.chain_response_support_valid[key] += 1
                if a_present and chain_response_valid:
                    stats.chain_response_valid[key] += 1

                # ChainPrecedence(a, b):
                # every B is immediately preceded by A
                chain_precedence_valid = not b_present or all(
                    b_pos > 0 and trace[b_pos - 1] == a for b_pos in positions[b]
                )
                if chain_precedence_valid:
                    stats.chain_precedence_support_valid[key] += 1
                if b_present and chain_precedence_valid:
                    stats.chain_precedence_valid[key] += 1

                # A absent/ B absent/ or every B occurs before the first A
                not_succession_valid = (
                    not a_present or not b_present or positions[b][-1] < positions[a][0]
                )
                if not_succession_valid:
                    stats.not_succession_support_valid[key] += 1
                if a_present and not_succession_valid:
                    stats.not_succession_valid[key] += 1

    return stats, activities


def activities_of_rule(rule) -> set:
    acts = set()
    for attr in ("target_activity", "activity", "activity_a", "activity_b"):
        if hasattr(rule, attr):
            value = getattr(rule, attr)
            if value is not None:
                acts.add(value)
    return acts


def can_possibly_imply(rule, others) -> bool:
    target_acts = activities_of_rule(rule)
    other_acts = set().union(*(activities_of_rule(r) for r in others))
    return bool(target_acts & other_acts)


def product_automaton(
    rules: List[AbstractRule],
    alphabet: Set[str],
    automata_by_rule: Dict[AbstractRule, DFA],
):
    if not rules:
        return DFA.universal_language(input_symbols=set(alphabet))
    dfas = [automata_by_rule[r] for r in rules]
    return reduce(lambda acc, aut: acc.intersection(aut), dfas)


def is_redundant(rule, remaining_rules, alphabet, accept_all: DFA, automata_by_rule):
    rule_acts = activities_of_rule(rule)
    relevant_others = [
        other
        for other in remaining_rules
        if other is not rule and rule_acts & activities_of_rule(other)
    ]
    if not can_possibly_imply(rule, relevant_others):
        return False

    others_automaton = product_automaton(relevant_others, alphabet, automata_by_rule)

    rule_dfa = rule.to_automaton(alphabet=alphabet)
    not_rule = NFA.from_dfa(accept_all.difference(rule_dfa))
    others_automaton = NFA.from_dfa(others_automaton)
    witness = others_automaton.intersection(not_rule)

    return len(witness.final_states) == 0


def minimize_rule_set(rules: List[AbstractRule], log: List[str]) -> List[AbstractRule]:
    # Resolving inconsistencies and redundancies in declarative process
    # C. Di Ciccio et al.
    alphabet = set([e for trace in log for e in trace])
    rule_to_sup_conf = {}
    accept_all = DFA.universal_language(input_symbols=set(alphabet))
    automata_by_rule = {r: r.to_automaton(alphabet=set(alphabet)) for r in rules}
    for r in rules:
        r.apply(log)
        try:
            sup = r.calc_support(log)
        except:
            sup = r.calc_support()
        try:
            conf = r.calc_confidence(log)
        except:
            conf = r.calc_confidence()
        rule_to_sup_conf[r] = (sup, conf)
    # The sorting algorithm
    sorted_rules = sorted(
        rules, key=lambda r: (rule_to_sup_conf[r][0], rule_to_sup_conf[r][1])
    )
    remaining_rules = list(sorted_rules)
    for r in list(remaining_rules):
        if r in remaining_rules and is_redundant(
            r, remaining_rules, alphabet, accept_all, automata_by_rule
        ):
            remaining_rules.remove(r)

    return remaining_rules


def rule_key(rule: AbstractRule) -> tuple[type, tuple]:
    return type(rule), tuple(rule.args)


def reduce_rule_hierarchies(
    rules: List[AbstractRule],
) -> List[AbstractRule]:
    redundant_keys: set[tuple[type, tuple]] = set()

    for rule in rules:
        if hasattr(rule, "target_activity"):
            if isinstance(rule, InitializationRule) or isinstance(rule, EndRule):
                # Existence is redundand
                a = rule.target_activity
                redundant_keys.add((ExistenceRule, (a,)))
        if not hasattr(rule, "activity_a") or not hasattr(rule, "activity_b"):
            continue
        a, b = rule.activity_a, rule.activity_b
        if a is None or b is None:
            continue
        if isinstance(rule, ChainResponseRule):
            redundant_keys.add((ResponseRule, (a, b)))
            redundant_keys.add((RespondedExistenceRule, (a, b)))

        elif isinstance(rule, ResponseRule):
            redundant_keys.add((RespondedExistenceRule, (a, b)))

        elif isinstance(rule, ChainPrecedenceRule):
            redundant_keys.add((PrecedenceRule, (a, b)))
            redundant_keys.add((RespondedExistenceRule, (b, a)))

        elif isinstance(rule, PrecedenceRule):
            redundant_keys.add((RespondedExistenceRule, (b, a)))

        elif isinstance(rule, NotCoExistenceRule):
            redundant_keys.add((NotSuccessionRule, (a, b)))
            redundant_keys.add((NotSuccessionRule, (b, a)))

    return [rule for rule in rules if rule_key(rule) not in redundant_keys]


def _find_cycle_nodes(edges: List[Tuple[str, str]]) -> Set[str]:
    """
    Returns every activity that belongs to a directed cycle
    """
    graph: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()

    for source, target in edges:
        graph[source].append(target)
        nodes.update((source, target))

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    cycle_nodes: set[str] = set()

    def strong_connect(node: str) -> None:
        nonlocal index

        indices[node] = index
        lowlinks[node] = index
        index += 1

        stack.append(node)
        on_stack.add(node)

        for neighbour in graph[node]:
            if neighbour not in indices:
                strong_connect(neighbour)
                lowlinks[node] = min(
                    lowlinks[node],
                    lowlinks[neighbour],
                )
            elif neighbour in on_stack:
                lowlinks[node] = min(
                    lowlinks[node],
                    indices[neighbour],
                )

        if lowlinks[node] != indices[node]:
            return

        component: set[str] = set()

        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)

            if member == node:
                break

        # More than one node in an SCC --> cycle detected
        if len(component) > 1:
            cycle_nodes.update(component)

        elif node in graph[node]:
            cycle_nodes.add(node)

    for node in nodes:
        if node not in indices:
            strong_connect(node)

    return cycle_nodes


def __identify_circularities(rules: List[AbstractRule]) -> Set[Tuple[str]]:
    response_rules = [
        r for r in rules if isinstance(r, (ChainResponseRule, ResponseRule))
    ]
    precedence_rules = [
        r for r in rules if isinstance(r, (ChainPrecedenceRule, PrecedenceRule))
    ]
    response_edges = [(rule.activity_a, rule.activity_b) for rule in response_rules]
    precedence_edges = [(rule.activity_a, rule.activity_b) for rule in precedence_rules]
    return _find_cycle_nodes(response_edges) | _find_cycle_nodes(precedence_edges)


def resolve_circularities(
    circularities: Set[str],
    remaining_rules: List[AbstractRule],
) -> List[AbstractRule]:
    changed = True
    rules_to_remove = []

    while changed:
        changed = False

        for rule in remaining_rules:
            previous_size = len(circularities)

            if hasattr(rule, "target_activity"):
                continue

            if (
                isinstance(
                    rule, (ChainResponseRule, ResponseRule, RespondedExistenceRule)
                )
                and rule.activity_b in circularities
            ):
                circularities.add(rule.activity_a)
                rules_to_remove.append(rule)

            elif (
                isinstance(
                    rule,
                    (
                        ChainPrecedenceRule,
                        PrecedenceRule,
                    ),
                )
                and rule.activity_a in circularities
            ):
                circularities.add(rule.activity_b)
                rules_to_remove.append(rule)

            elif isinstance(rule, CoExistenceRule) and (
                rule.activity_a in circularities or rule.activity_b in circularities
            ):
                circularities.update((rule.activity_a, rule.activity_b))
                rules_to_remove.append(rule)
            elif isinstance(rule, (NotCoExistenceRule, NotSuccessionRule)) and (
                rule.activity_a in circularities or rule.activity_b in circularities
            ):
                # This is trivially satisfied so we can just minimize the rule set without caring
                rules_to_remove.append(rule)
            if len(circularities) > previous_size:
                changed = True
    return [rule for rule in remaining_rules if rule not in rules_to_remove]


def preprocess_rule_set(
    rules: List[AbstractRule], log: List[str]
) -> Tuple[List[AbstractRule], List[str]]:
    """
    Identifies parts of the rule set that are optional/should be removed
    and modifies the list of rules and event log accordingly
    """
    alphabet = {e for trace in log for e in trace}
    automata_by_rule = {r: r.to_automaton(alphabet=set(alphabet)) for r in rules}
    product = product_automaton(rules, alphabet, automata_by_rule)
    if not len(product.final_states):
        raise Exception(
            f"Product automaton is empty, the set of rules is unsatisfiable."
        )

    rules_to_remove = []
    rules_to_add = []
    # First, merge patterns from type NotSuccession(a,b) \land NotSuccession(b,a) into NotCoExistence(a,b)
    not_succession_rules = [r for r in rules if isinstance(r, NotSuccessionRule)]
    for i in range(len(not_succession_rules) - 1):
        for j in range(i + 1, len(not_succession_rules)):
            rule_i = not_succession_rules[i]
            rule_j = not_succession_rules[j]
            a_i, b_i = rule_i.activity_a, rule_i.activity_b
            a_j, b_j = rule_j.activity_a, rule_j.activity_b
            if (a_i == b_j) and (a_j == b_i):
                rules_to_remove.extend([rule_i, rule_j])
                rules_to_add.append(NotCoExistenceRule(a_i, b_i))
    remaining_rules = [r for r in rules if r not in rules_to_remove]
    remaining_rules.extend(rules_to_add)
    existence = {r.target_activity for r in rules if isinstance(r, ExistenceRule)}

    conflicts = {
        r.activity_b if r.activity_a in existence else r.activity_a
        for r in remaining_rules
        if isinstance(r, NotCoExistenceRule)
        and (r.activity_a in existence or r.activity_b in existence)
    }
    rules_to_remove.extend(
        [
            r
            for r in remaining_rules
            if isinstance(r, NotCoExistenceRule)
            and (r.activity_a in existence or r.activity_b in existence)
        ]
    )
    remaining_rules = [r for r in remaining_rules if r not in rules_to_remove]
    # Check for circularities, e.g., Response(a,b) \land Response(b,a) or Precedence(a,b) \land Precedence(b,a) (remove the rules, remove depending constraints, remove acts from the log)
    circularities = __identify_circularities(remaining_rules)
    conflicts = conflicts | circularities

    if conflicts:
        conflicts = conflicts | circularities

        remaining_rules = resolve_circularities(conflicts, remaining_rules)
    # Preprocess the log
    print(f"The remaining rules are: {rules}, conflicts are: {conflicts}")
    modified_log = []
    for trace in log:
        new_trace = [e for e in trace if e not in conflicts]
        modified_log.append(new_trace)
    log = modified_log
    # In the end, get rid of redundant activities using the hierarchy
    # And the automaton-based redundancy check
    return minimize_rule_set(reduce_rule_hierarchies(remaining_rules), log), log
