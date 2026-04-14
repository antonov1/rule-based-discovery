from collections import Counter
from typing import List

import pandas as pd
from rules import (
    AbstractRule,
    AtMostOnceRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)


def extract_rules_from_data(
    data: pd.DataFrame,
    case_id_col: str = "case:concept:name",
    activity_col: str = "concept:name",
):
    # Convert the DataFrame to an event log
    cases = data[case_id_col].unique()
    traces = []
    for case in cases:
        case_data = data[data[case_id_col] == case].sort_values(by="time:timestamp")
        trace = case_data[activity_col].tolist()
        traces.append(trace)


def check_start_end(log, min_support: float = 0.5):
    non_empty_traces = [trace for trace in log if trace]
    total_traces = len(non_empty_traces)

    if total_traces == 0:
        return {"init_rules": [], "end_rules": []}

    start_counts = Counter(trace[0] for trace in non_empty_traces)
    end_counts = Counter(trace[-1] for trace in non_empty_traces)
    init_rules = []
    for activity, count in start_counts.items():
        support = count / total_traces
        confidence = count / total_traces
        if support >= min_support:
            init_rules.append((activity, support, confidence))

    end_rules = []
    for activity, count in end_counts.items():
        support = count / total_traces
        confidence = count / total_traces
        if support >= min_support:
            end_rules.append((activity, support, confidence))
    return {"init_rules": init_rules, "end_rules": end_rules}


def extract(log, min_support: float, min_confidence: float) -> List[AbstractRule]:
    extracted_rules = []

    se_rules = check_start_end(log, min_support=min_support)

    for activity, _, _ in se_rules["init_rules"]:
        rule = InitializationRule(activity)
        rule.apply(log)
        if (
            rule.calc_support() >= min_support
            and rule.calc_confidence() >= min_confidence
        ):
            extracted_rules.append(rule)

    for activity, _, _ in se_rules["end_rules"]:
        rule = EndRule(activity)
        rule.apply(log)
        if (
            rule.calc_support() >= min_support
            and rule.calc_confidence() >= min_confidence
        ):
            extracted_rules.append(rule)
    unary_activities = sorted(set(a for trace in log for a in trace))
    binary_pairs = {
        (a, b) for a in unary_activities for b in unary_activities if a != b
    }

    for act in sorted(unary_activities):
        for rule_cls in [ExistenceRule, AtMostOnceRule]:
            rule = rule_cls(act)
            rule.apply(log)
            if (
                rule.calc_support() >= min_support
                and rule.calc_confidence() >= min_confidence
            ):
                extracted_rules.append(rule)

    seen = set()
    for pair in binary_pairs:
        if len(pair) != 2:
            continue

        a, b = pair

        candidate_rules = [
            CoExistenceRule(a, b),
            RespondedExistenceRule(a, b),
            RespondedExistenceRule(b, a),
            ResponseRule(a, b),
            ResponseRule(b, a),
            PrecedenceRule(a, b),
            PrecedenceRule(b, a),
            ChainResponseRule(a, b),
            ChainResponseRule(b, a),
            ChainPrecedenceRule(a, b),
            ChainPrecedenceRule(b, a),
        ]

        for rule in candidate_rules:
            key = (rule.__class__.__name__, tuple(rule.args))
            if key in seen:
                continue
            seen.add(key)

            rule.apply(log)
            if (
                rule.calc_support() >= min_support
                and rule.calc_confidence(log) >= min_confidence
            ):
                extracted_rules.append(rule)

    return extracted_rules


# Example usage
if __name__ == "__main__":
    dataset = [
        [
            "A",
            "B",
            "C",
            "D",
            "A",
        ],
        ["E", "F", "G"],
        ["A", "C", "E", "A"],
        ["B", "D", "F"],
    ]
    rules = extract(dataset, 0.5, 0.5)
    for rule in rules:
        print(rule)
        print(rule.get_confidence())
