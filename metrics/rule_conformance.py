from typing import List

import pm4py
from pm4py.algo.simulation.playout.process_tree.variants.basic_playout import (
    apply as playout_apply,
)
from pm4py.objects.process_tree.obj import ProcessTree
from rules import AbstractRule


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def apply(model: ProcessTree, rules: List[AbstractRule]):
    playout = pm4py.convert_to_dataframe(playout_apply(model))
    playout = preprocess_log(playout)
    unsat_rules = []
    for rule in rules:
        sat = rule.apply(playout)
        if sat != playout:
            unsat_rules.append(rule)
    val = 1 - len(unsat_rules) / len(rules) if rules else 1
    return val, unsat_rules
