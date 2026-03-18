from collections import Counter
from typing import List

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from rules import (
    AbstractRule,
    AtMostOnceRule,
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


def rule_mining(
    log, min_support: float = 0.5, min_confidence: float = 0.7, rule_size: int = 2
):
    te = TransactionEncoder()
    te_ary = te.fit(log).transform(log)
    df = pd.DataFrame(te_ary, columns=te.columns_)
    frequent_itemsets = apriori(df, min_support=min_support, use_colnames=True)
    frequent_itemsets["length"] = frequent_itemsets["itemsets"].apply(lambda x: len(x))
    frequent_itemsets = frequent_itemsets[frequent_itemsets["length"] <= rule_size]
    rules = association_rules(
        frequent_itemsets, metric="confidence", min_threshold=min_confidence
    )
    return rules[["antecedents", "consequents", "support", "confidence", "lift"]]


def extract(log, min_support: float, min_confidence: float) -> List[AbstractRule]:
    extracted_rules = []

    se_rules = check_start_end(log, min_support=min_support)

    for activity, _, _ in se_rules["init_rules"]:
        rule = InitializationRule([activity])
        rule.apply(log)
        if (
            rule.calc_support() >= min_support
            and rule.calc_confidence() >= min_confidence
        ):
            extracted_rules.append(rule)

    for activity, _, _ in se_rules["end_rules"]:
        rule = EndRule([activity])
        rule.apply(log)
        if (
            rule.calc_support() >= min_support
            and rule.calc_confidence() >= min_confidence
        ):
            extracted_rules.append(rule)
    mined = rule_mining(
        log,
        min_support=min_support,
        min_confidence=min_confidence,
        rule_size=2,
    )
    unary_activities = set([a for trace in log for a in trace])
    binary_pairs = set()

    # frozensets from mlxtend
    for _, row in mined.iterrows():
        antecedents = set(row["antecedents"])
        consequents = set(row["consequents"])

        all_acts = antecedents | consequents

        if len(all_acts) == 2:
            a, b = sorted(all_acts)
            binary_pairs.add((a, b))
            # directional candidates too
            if len(antecedents) == 1 and len(consequents) == 1:
                x = next(iter(antecedents))
                y = next(iter(consequents))
                binary_pairs.add((x, y))

    for act in sorted(unary_activities):
        for rule_cls in [ExistenceRule, AtMostOnceRule]:
            rule = rule_cls([act])
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
            CoExistenceRule([a, b]),
            RespondedExistenceRule([a, b]),
            RespondedExistenceRule([b, a]),
            ResponseRule([a, b]),
            ResponseRule([b, a]),
            PrecedenceRule([a, b]),
            PrecedenceRule([b, a]),
        ]

        for rule in candidate_rules:
            key = (rule.__class__.__name__, tuple(rule.activities))
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
    print(rules)
