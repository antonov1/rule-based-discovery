from typing import List, Set

import pm4py
from automata.fa.dfa import DFA
from automata.fa.nfa import NFA
from pm4py.algo.simulation.playout.petri_net.algorithm import (
    apply as playout_apply,
    Variants as PlayoutVariants,
)
from pm4py.objects.bpmn.obj import BPMN
from pm4py.objects.process_tree.obj import ProcessTree
from pm4py.objects.transition_system.obj import TransitionSystem
from rules import AbstractRule


def weighted_conformance(
    model: ProcessTree,
    rules: List[AbstractRule],
    alphabet: Set[str],
    log: List[List[str]],
):
    if not len(rules):
        return 1
    ts = pm4py.convert.convert_to_reachability_graph(model)
    for r in rules or []:
        if hasattr(r, "target_activity"):
            alphabet.add(r.target_activity)
        if hasattr(r, "activity_a"):
            alphabet.add(r.activity_a)
        if hasattr(r, "activity_b"):
            alphabet.add(r.activity_b)

    nfa = transition_system_to_nfa(ts, alphabet=alphabet)
    # constructing accept_all automaton
    sup_unsat = []
    unsat_rules = []
    sup_all = []

    accept_all = DFA.universal_language(input_symbols=set(alphabet))
    for rule in rules:
        rule_automaton = rule.to_automaton(alphabet=alphabet)
        rule.apply(log)
        try:
            sup = rule.calc_support(log)
        except:
            sup = rule.calc_support()
        sup_all.append(sup)
        # to check, we need to see if the intersection of the model automaton and the negation of the rule automaton is empty
        negated_rule_automaton = NFA.from_dfa(accept_all.difference(rule_automaton))
        intersection = nfa.intersection(negated_rule_automaton)
        if len(intersection.final_states) > 0:
            sup_unsat.append(sup)
            unsat_rules.append(rule)
    return 1 - sum(sup_unsat) / len(rules) * max(sup_all), unsat_rules


def conformance(
    model: ProcessTree | BPMN, rules: List[AbstractRule], alphabet: Set[str]
):
    if not len(rules):
        return 1
    ts = pm4py.convert.convert_to_reachability_graph(model)
    for r in rules or []:
        if hasattr(r, "target_activity"):
            alphabet.add(r.target_activity)
        if hasattr(r, "activity_a"):
            alphabet.add(r.activity_a)
        if hasattr(r, "activity_b"):
            alphabet.add(r.activity_b)

    nfa = transition_system_to_nfa(ts, alphabet=alphabet)
    # constructing accept_all automaton
    unsat_rules = []
    accept_all = DFA.universal_language(input_symbols=set(alphabet))

    for rule in rules:
        rule_automaton = rule.to_automaton(alphabet=alphabet)
        # to check, we need to see if the intersection of the model automaton and the negation of the rule automaton is empty
        negated_rule_automaton = NFA.from_dfa(accept_all.difference(rule_automaton))
        intersection = nfa.intersection(negated_rule_automaton)
        if len(intersection.final_states) > 0:
            unsat_rules.append(rule)
    return 1 - len(unsat_rules) / len(rules), unsat_rules


def __extract_symbol(label, epsilon_symbol=""):
    if label is None:
        return epsilon_symbol
    label = str(label).strip()
    # PM4Py saves the labels as strings, not tuples
    # so here it is a bit ad-hoc
    if label.startswith("(") and label.endswith(")") and "," in label:
        activity = label.rsplit(",", 1)[1].strip().rstrip(")")
        if activity == "None":
            return epsilon_symbol

        return activity.strip("'\"")
    return label


def transition_system_to_nfa(
    ts: TransitionSystem,
    alphabet: Set[str],
    initial_state: str = "source1",
    sink_state: str = "sink1",
    epsilon_symbol: str = "",
) -> NFA:
    # returns an epsilon-NFA that accepts the same language as the transition system
    states = {str(state.name) for state in ts.states}
    if sink_state not in states or initial_state not in states:
        raise ValueError("Sink or initial state are not part of states")
    transitions = {state: {} for state in states}
    for edge in ts.transitions:
        source = str(edge.from_state.name)
        target = str(edge.to_state.name)

        if source not in states:
            raise ValueError(f"Transition source {source!r} is not in states.")

        if target not in states:
            raise ValueError(f"Transition target {target!r} is not in states.")

        symbol = __extract_symbol(edge.name, epsilon_symbol=epsilon_symbol)

        if symbol != epsilon_symbol and symbol not in alphabet:
            raise ValueError(
                f"Transition label {symbol!r} is not in the provided alphabet {alphabet}."
            )

        transitions[source].setdefault(symbol, set()).add(target)
    return NFA(
        states=states,
        input_symbols=set(alphabet),
        transitions=transitions,
        initial_state=initial_state,
        final_states={sink_state},
    )


# ------ Simulation-based results ------- #


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def apply(model: ProcessTree, rules: List[AbstractRule]):
    net, im, fm = pm4py.convert_to_petri_net(model)
    playout = pm4py.convert_to_dataframe(
        playout_apply(net, im, fm, variant=PlayoutVariants.BASIC_PLAYOUT)
    )
    playout = preprocess_log(playout)
    unsat_rules = []
    playout_set = {tuple(trace) for trace in playout}
    {act for trace in playout for act in trace}
    for rule in rules:
        sat = rule.apply(playout)
        sat_set = {tuple(trace) for trace in sat}
        bad = playout_set - sat_set
        if bad:
            unsat_rules.append(rule)
            # print(
            #    f"Rule {rule} is not satisfied, the event log has the following activities: {acts}. Counterexamples: {bad}"
            # )
    val = 1 - len(unsat_rules) / len(rules) if rules else 1
    return val, unsat_rules
