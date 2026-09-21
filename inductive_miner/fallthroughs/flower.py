from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import AtMostOnceRule, ExistenceRule


def build_flower_tree(activities):
    loop = ProcessTree(operator=Operator.LOOP)

    tau = ProcessTree(label=None)
    xor = ProcessTree(operator=Operator.XOR)

    tau.parent = loop
    xor.parent = loop
    loop.children = [tau, xor]

    for activity in sorted(activities):
        leaf = ProcessTree(label=activity)
        leaf.parent = xor
        xor.children.append(leaf)

    return loop


def apply(log, rules=None, **kwargs):
    rules = rules or []

    activities = sorted({activity for trace in log for activity in trace})

    if len(activities) < 2:
        return None

    existence_activities = {
        rule.target_activity
        for rule in rules
        if isinstance(rule, ExistenceRule) and rule.target_activity in activities
    }

    at_most_once_activities = {
        rule.target_activity
        for rule in rules
        if isinstance(rule, AtMostOnceRule) and rule.target_activity in activities
    }

    constrained_activities = existence_activities | at_most_once_activities

    if not constrained_activities:
        return build_flower_tree(activities)

    remaining_activities = set(activities) - constrained_activities

    sublogs = []
    projected_rules = []

    for activity in sorted(constrained_activities):
        if activity in existence_activities:
            synthetic_log = [[activity]]
        else:
            synthetic_log = [[], [activity]]

        sublogs.append(synthetic_log)

        activity_rules = [
            rule
            for rule in rules
            if isinstance(rule, (ExistenceRule, AtMostOnceRule))
            and rule.target_activity == activity
        ]

        projected_rules.append(activity_rules)

    if remaining_activities:
        remaining_log = [
            [event for event in trace if event in remaining_activities] for trace in log
        ]

        remaining_rules = [
            rule
            for rule in rules
            if not (
                isinstance(rule, (ExistenceRule, AtMostOnceRule))
                and rule.target_activity in constrained_activities
            )
        ]

        sublogs.append(remaining_log)
        projected_rules.append(remaining_rules)

    return Decomposition(
        operator=Operator.PARALLEL,
        sublogs=sublogs,
        projected_rules=projected_rules,
    )
