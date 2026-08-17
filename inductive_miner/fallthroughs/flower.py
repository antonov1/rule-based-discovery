from inductive_miner.cuts import LoopCut
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator
from rules import AtMostOnceRule, ExistenceRule


def same_rules(rules_a, rules_b):
    return sorted(map(str, rules_a or [])) == sorted(map(str, rules_b or []))


def apply(
    log,
    rules=None,
    **kwargs,
) -> Decomposition:
    rules = rules or []

    activities = sorted({activity for trace in log for activity in trace})

    if len(activities) < 2:
        return None

    mandatory = {
        rule.target_activity
        for rule in rules
        if isinstance(rule, (AtMostOnceRule, ExistenceRule))
        and rule.target_activity in activities
    }

    if mandatory:
        remaining = set(activities) - mandatory

        sublogs = []
        projected_rules = []

        # One branch per existence/atmost1 constraint
        for activity in sorted(mandatory):
            projected_log = [
                [event for event in trace if event == activity] for trace in log
            ]

            sublogs.append(projected_log)

            projected_rules.append(
                [
                    rule
                    for rule in rules
                    if isinstance(rule, (AtMostOnceRule, ExistenceRule))
                    and rule.target_activity == activity
                ]
            )

        if remaining:
            remaining_log = [
                [event for event in trace if event in remaining] for trace in log
            ]

            sublogs.append(remaining_log)

            remaining_rules = [
                rule
                for rule in rules
                if not (
                    isinstance(rule, AtMostOnceRule)
                    and rule.target_activity in mandatory
                )
            ]

            projected_rules.append(remaining_rules)

        return Decomposition(
            operator=Operator.PARALLEL,
            sublogs=sublogs,
            projected_rules=projected_rules,
        )

    # The stadnard flower
    redo_log = [[a] for a in activities]
    groups = [set(), set(activities)]
    redo_rules = LoopCut.project_rules(rules, groups) if rules else None

    if redo_log == log and same_rules(redo_rules[1], rules):
        return None
    return Decomposition(
        operator=Operator.LOOP,
        sublogs=[[], redo_log],
        projected_rules=redo_rules,
    )
