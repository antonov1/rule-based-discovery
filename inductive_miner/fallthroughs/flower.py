from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AtMostOnceRule


def same_rules(rules_a, rules_b):
    return sorted(map(str, rules_a or [])) == sorted(map(str, rules_b or []))


def build_flower_tree(activities):
    """
    Build the terminal flower model:

        *(tau, X(a, b, c, ...))

    No recursive mining is performed below this tree.
    """
    loop = ProcessTree(operator=Operator.LOOP)

    tau = ProcessTree(label=None)
    xor = ProcessTree(operator=Operator.XOR)

    tau.parent = loop
    xor.parent = loop
    loop.children = [tau, xor]

    for activity in activities:
        leaf = ProcessTree(label=activity)
        leaf.parent = xor
        xor.children.append(leaf)

    return loop


def apply(
    log,
    rules=None,
    **kwargs,
):
    rules = rules or []

    activities = sorted({activity for trace in log for activity in trace})

    if len(activities) < 2:
        return None

    at_most_once = {
        rule.target_activity
        for rule in rules
        if isinstance(rule, AtMostOnceRule) and rule.target_activity in activities
    }

    if at_most_once:
        remaining = set(activities) - at_most_once

        sublogs = []
        projected_rules = []

        for activity in sorted(at_most_once):
            projected_log = [
                [event for event in trace if event == activity] for trace in log
            ]

            sublogs.append(projected_log)

            projected_rules.append(
                [
                    rule
                    for rule in rules
                    if isinstance(rule, AtMostOnceRule)
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
                    and rule.target_activity in at_most_once
                )
            ]

            projected_rules.append(remaining_rules)

        return Decomposition(
            operator=Operator.PARALLEL,
            sublogs=sublogs,
            projected_rules=projected_rules,
        )

    return build_flower_tree(activities)
