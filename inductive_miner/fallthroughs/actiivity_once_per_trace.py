from typing import List, Optional, Set, Tuple

import networkx as nx
from inductive_miner.cuts import ConcurrentCut
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator
from rules import AbstractRule


def detect(
    log: List[List[str]],
    rules: List[AbstractRule] = None,
) -> Tuple[Optional[str], Set[AbstractRule]]:
    if not log:
        return None, set()

    alphabet = {activity for trace in log for activity in trace}

    candidate_activities = set(log[0])

    for trace in log:
        for activity in list(candidate_activities):
            if trace.count(activity) != 1:
                candidate_activities.remove(activity)

    candidates = sorted(candidate_activities)
    unsat_rules = None

    for candidate in candidates:
        if not rules:
            return candidate, set()

        violations = ConcurrentCut.check_rules(
            rules,
            [
                {candidate},
                alphabet - {candidate},
            ],
        )

        if not violations:
            return candidate, set()

        if not unsat_rules:
            unsat_rules = violations

    return None, unsat_rules


def project(
    log: List[List[str]],
    candidate: str,
):
    candidate_log = [
        [activity for activity in trace if activity == candidate] for trace in log
    ]

    remaining_log = [
        [activity for activity in trace if activity != candidate] for trace in log
    ]

    return candidate_log, remaining_log


def apply(
    log: List[List[str]],
    dfg: nx.DiGraph,
    rules: List[AbstractRule] = None,
    **kwargs,
):
    rules = rules or []

    alphabet = {activity for trace in log for activity in trace}

    if len(alphabet) <= 1:
        return None

    candidate, unsat_rules = detect(
        log,
        rules,
    )

    if candidate is None:
        return unsat_rules

    groups = [
        {candidate},
        alphabet - {candidate},
    ]

    projected_rules = (
        ConcurrentCut.project_rules(
            rules,
            groups,
        )
        if rules
        else [[], []]
    )

    projected_logs = project(
        log,
        candidate,
    )

    return Decomposition(
        operator=Operator.PARALLEL,
        sublogs=projected_logs,
        projected_rules=projected_rules,
    )
