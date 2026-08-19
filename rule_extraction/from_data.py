from itertools import combinations, permutations
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
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)
from rules.rule_utils import (
    Activity,
    build_log_stats,
    LogStats,
    minimize_rule_set,
    reduce_rule_hierarchies,
)


def ratio(numerator: int, denominator: int, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def existence_metrics(stats: LogStats, activity: Activity) -> tuple[float, float]:
    valid = stats.activity_trace_count[activity]
    support = ratio(valid, stats.trace_count)
    return support, support


def at_most_once_metrics(
    stats: LogStats,
    activity: Activity,
) -> tuple[float, float]:
    support = ratio(
        stats.activity_at_most_once_valid[activity],
        stats.trace_count,
    )
    return support, support


def init_metrics(stats: LogStats, activity: Activity) -> tuple[float, float]:
    support = ratio(stats.start_count[activity], stats.trace_count)
    return support, support


def end_metrics(stats: LogStats, activity: Activity) -> tuple[float, float]:
    support = ratio(stats.end_count[activity], stats.trace_count)
    return support, support


def responded_existence_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.responded_existence_support_valid[key],
        stats.trace_count,
    )

    count_a = stats.activity_trace_count[a]
    confidence = ratio(
        stats.responded_existence_valid[key],
        count_a,
        default=1.0,
    )

    return support, confidence


def response_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.response_support_valid[key],
        stats.trace_count,
    )

    confidence = ratio(
        stats.response_valid[key],
        stats.activity_trace_count[a],
        default=1.0,
    )

    return support, confidence


def chain_response_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.chain_response_support_valid[key],
        stats.trace_count,
    )

    confidence = ratio(
        stats.chain_response_valid[key],
        stats.activity_trace_count[a],
        default=1.0,
    )

    return support, confidence


def precedence_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.precedence_support_valid[key],
        stats.trace_count,
    )

    confidence = ratio(
        stats.precedence_valid[key],
        stats.activity_trace_count[b],
        default=1.0,
    )

    return support, confidence


def chain_precedence_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.chain_precedence_support_valid[key],
        stats.trace_count,
    )

    confidence = ratio(
        stats.chain_precedence_valid[key],
        stats.activity_trace_count[b],
        default=1.0,
    )

    return support, confidence


def not_succession_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    key = (a, b)

    support = ratio(
        stats.not_succession_support_valid[key],
        stats.trace_count,
    )

    count_a = stats.activity_trace_count[a]
    confidence = ratio(
        stats.not_succession_valid[key],
        count_a,
        default=0.0,
    )

    return support, confidence


def coexistence_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    both = stats.co_existence_count[frozenset((a, b))]

    neither = (
        stats.trace_count
        - stats.activity_trace_count[a]
        - stats.activity_trace_count[b]
        + both
    )

    valid_traces = both + neither
    support = ratio(valid_traces, stats.trace_count)

    activated = stats.activity_trace_count[a] + stats.activity_trace_count[b] - both
    confidence = ratio(both, activated, default=1.0)

    return support, confidence


def not_coexistence_metrics(
    stats: LogStats,
    a: Activity,
    b: Activity,
) -> tuple[float, float]:
    both = stats.co_existence_count[frozenset((a, b))]

    valid_traces = stats.trace_count - both
    support = ratio(valid_traces, stats.trace_count)

    confidence = ratio(
        stats.activity_trace_count[a] + stats.activity_trace_count[b] - both,
        stats.activity_trace_count[a] + stats.activity_trace_count[b],
        default=0.0,
    )

    return support, confidence


def passes_thresholds(
    support: float,
    confidence: float,
    min_support: float,
    min_confidence: float,
) -> bool:
    return support >= min_support and confidence >= min_confidence


def add_rule(
    extracted_rules: List[AbstractRule],
    rule: AbstractRule,
    stats: LogStats,
    support: float,
    confidence: float,
) -> None:
    """
    Populate the existing rule object with metrics computed from LogStats.

    valid_traces_len is reconstructed from support because:

        support = valid_traces_len / trace_count
    """
    rule.data_len = stats.trace_count
    rule.valid_traces_len = round(support * stats.trace_count)
    rule.sup = support
    rule.conf = confidence

    extracted_rules.append(rule)


def evaluate_and_add(
    extracted_rules: List[AbstractRule],
    rule: AbstractRule,
    stats: LogStats,
    metrics: tuple[float, float],
    min_support: float,
    min_confidence: float,
) -> bool:
    """
    Returns True when the rule passes both thresholds.

    The return value is used to decide whether stronger descendants
    in the Declare hierarchy need to be evaluated.
    """
    support, confidence = metrics

    if not passes_thresholds(
        support,
        confidence,
        min_support,
        min_confidence,
    ):
        return False

    add_rule(
        extracted_rules,
        rule,
        stats,
        support,
        confidence,
    )

    return True


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def extract(
    log, min_support: float, min_confidence: float, chain_rules: bool = True
) -> List[AbstractRule]:
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(log)
    stats, activities = build_log_stats(log)

    extracted_rules: List[AbstractRule] = []

    # Unary constraints

    for activity in activities:
        evaluate_and_add(
            extracted_rules,
            InitializationRule(activity),
            stats,
            init_metrics(stats, activity),
            min_support,
            min_confidence,
        )

        evaluate_and_add(
            extracted_rules,
            EndRule(activity),
            stats,
            end_metrics(stats, activity),
            min_support,
            min_confidence,
        )

        evaluate_and_add(
            extracted_rules,
            ExistenceRule(activity),
            stats,
            existence_metrics(stats, activity),
            min_support,
            min_confidence,
        )

        evaluate_and_add(
            extracted_rules,
            AtMostOnceRule(activity),
            stats,
            at_most_once_metrics(stats, activity),
            min_support,
            min_confidence,
        )

    # Directed binary constraints

    for a, b in permutations(activities, 2):

        # Exploit the hierarchy defined by Di Ceccio et al. (2016) to avoid evaluating rules that are guaranteed to fail
        responded_passed = evaluate_and_add(
            extracted_rules,
            RespondedExistenceRule(a, b),
            stats,
            responded_existence_metrics(stats, a, b),
            min_support,
            min_confidence,
        )

        if responded_passed:
            response_passed = evaluate_and_add(
                extracted_rules,
                ResponseRule(a, b),
                stats,
                response_metrics(stats, a, b),
                min_support,
                min_confidence,
            )

            if response_passed and chain_rules:
                evaluate_and_add(
                    extracted_rules,
                    ChainResponseRule(a, b),
                    stats,
                    chain_response_metrics(stats, a, b),
                    min_support,
                    min_confidence,
                )

        # Precedence hierarchy
        precedence_root_support, precedence_root_confidence = (
            responded_existence_metrics(stats, b, a)
        )

        if passes_thresholds(
            precedence_root_support,
            precedence_root_confidence,
            min_support,
            min_confidence,
        ):
            precedence_passed = evaluate_and_add(
                extracted_rules,
                PrecedenceRule(a, b),
                stats,
                precedence_metrics(stats, a, b),
                min_support,
                min_confidence,
            )

            if precedence_passed and chain_rules:
                evaluate_and_add(
                    extracted_rules,
                    ChainPrecedenceRule(a, b),
                    stats,
                    chain_precedence_metrics(stats, a, b),
                    min_support,
                    min_confidence,
                )

        evaluate_and_add(
            extracted_rules,
            NotSuccessionRule(a, b),
            stats,
            not_succession_metrics(stats, a, b),
            min_support,
            min_confidence,
        )

    for a, b in combinations(activities, 2):

        evaluate_and_add(
            extracted_rules,
            CoExistenceRule(a, b),
            stats,
            coexistence_metrics(stats, a, b),
            min_support,
            min_confidence,
        )

        not_succession_ab_support, _ = not_succession_metrics(
            stats,
            a,
            b,
        )

        not_succession_ba_support, _ = not_succession_metrics(
            stats,
            b,
            a,
        )

        if (
            not_succession_ab_support >= min_support
            and not_succession_ba_support >= min_support
        ):
            evaluate_and_add(
                extracted_rules,
                NotCoExistenceRule(a, b),
                stats,
                not_coexistence_metrics(stats, a, b),
                min_support,
                min_confidence,
            )

    reduced = reduce_rule_hierarchies(extracted_rules)
    return minimize_rule_set(reduced, log)


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
    print(
        f"Before reduction: {len(extract(dataset, min_support=0.76, min_confidence=0.76))} rules"
    )
