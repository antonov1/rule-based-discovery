from enum import Enum
from typing import Any, Callable, List

import numpy as np
import pandas as pd
import pm4py
from inductive_miner.im_utils import normalize_tree
from rules import AbstractRule


class Variants(Enum):
    Alignment = "Alignment"
    TokenBased = "TokenBased"


def generalization_kfold(
    log: pd.DataFrame,
    algorithm: Callable[[Any], Any],
    rules: List[AbstractRule],
    k=3,
    type: Variants = Variants.Alignment,
):
    # split the log into k folds
    folds = np.array_split(log["case:concept:name"], k)
    generalization = []
    for i in range(k):
        ids = folds[i]
        current_log = log[log["case:concept:name"].isin(ids)]
        ptree = normalize_tree(algorithm(current_log, rules))

        net, im, fm = pm4py.convert_to_petri_net(ptree)
        fitness_fold = (
            pm4py.conformance.fitness_alignments(current_log, net, im, fm)[
                "averageFitness"
            ]
            if type == Variants.Alignment
            else pm4py.conformance.fitness_token_based_replay(current_log, net, im, fm)[
                "log_fitness"
            ]
        )
        precision_log = (
            pm4py.conformance.precision_alignments(current_log, net, im, fm)
            if type == Variants.Alignment
            else pm4py.conformance.precision_token_based_replay(
                current_log, net, im, fm
            )
        )
        generalization.append(
            2 * fitness_fold * precision_log / (fitness_fold + precision_log)
        )
    return np.mean(generalization)
