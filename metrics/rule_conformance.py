from typing import List

import pm4py
from pm4py.algo.simulation.playout.petri_net.algorithm import (
    apply as playout_apply,
    Variants as PlayoutVariants,
)
from pm4py.objects.process_tree.obj import ProcessTree
from rules import AbstractRule


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
    acts = {act for trace in playout for act in trace}
    for rule in rules:
        sat = rule.apply(playout)
        sat_set = {tuple(trace) for trace in sat}
        bad = playout_set - sat_set
        if bad:
            unsat_rules.append(rule)
            print(
                f"Rule {rule} is not satisfied, the event log has the following activities: {acts}. Counterexamples: {bad}"
            )
    val = 1 - len(unsat_rules) / len(rules) if rules else 1
    return val, unsat_rules
