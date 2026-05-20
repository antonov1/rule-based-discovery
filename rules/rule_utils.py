from functools import reduce
from typing import Dict, List, Set

from automata.fa.dfa import DFA
from automata.fa.nfa import NFA
from rules.abstract_rule import AbstractRule


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
