from itertools import combinations
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
    build_log_stats,
    LogStats,
    minimize_rule_set,
    reduce_rule_hierarchies,
)


def ratio(
    numerator: int,
    denominator: int,
    default: float = 0.0,
) -> float:
    return numerator / denominator if denominator else default


def add_rule(
    extracted_rules: List[AbstractRule],
    rule: AbstractRule,
    stats: LogStats,
    valid_traces: int,
    support: float,
    confidence: float,
) -> None:
    """
    Add a rule whose support/confidence have already passed the thresholds.
    """
    rule.data_len = stats.trace_count
    rule.valid_traces_len = valid_traces
    rule.sup = support
    rule.conf = confidence
    extracted_rules.append(rule)


def passes_thresholds(
    support: float,
    confidence: float,
    min_support: float,
    min_confidence: float,
) -> bool:
    return support >= min_support and confidence >= min_confidence


def preprocess_log(
    log,
    activity_key: str = "concept:name",
    case_key: str = "case:concept:name",
):
    return log.groupby(case_key, sort=False)[activity_key].apply(list).tolist()


def extract(
    log,
    min_support: float,
    min_confidence: float,
    chain_rules: bool = True,
) -> List[AbstractRule]:
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(log)

    stats, activities = build_log_stats(log)

    extracted_rules: List[AbstractRule] = []

    trace_count = stats.trace_count
    activity_trace_count = stats.activity_trace_count

    # Unary constraints

    for activity in activities:
        count = activity_trace_count[activity]

        unary_candidates = (
            (
                InitializationRule,
                stats.start_count[activity],
            ),
            (
                EndRule,
                stats.end_count[activity],
            ),
            (
                ExistenceRule,
                count,
            ),
            (
                AtMostOnceRule,
                stats.activity_at_most_once_valid[activity],
            ),
        )

        for rule_type, valid_traces in unary_candidates:
            support = ratio(valid_traces, trace_count)

            # For these unary rules confidence == support.
            if support < min_support or support < min_confidence:
                continue

            add_rule(
                extracted_rules,
                rule_type(activity),
                stats,
                valid_traces,
                support,
                support,
            )

    # Binary constraints

    for a, b in combinations(activities, 2):
        key_ab = (a, b)
        key_ba = (b, a)

        count_a = activity_trace_count[a]
        count_b = activity_trace_count[b]

        re_valid_traces_ab = stats.responded_existence_support_valid[key_ab]
        re_support_ab = ratio(re_valid_traces_ab, trace_count)
        re_conf_ab = ratio(
            stats.responded_existence_valid[key_ab],
            count_a,
            default=1.0,
        )
        re_passed_ab = passes_thresholds(
            re_support_ab,
            re_conf_ab,
            min_support,
            min_confidence,
        )

        if re_passed_ab:
            add_rule(
                extracted_rules,
                RespondedExistenceRule(a, b),
                stats,
                re_valid_traces_ab,
                re_support_ab,
                re_conf_ab,
            )

        re_valid_traces_ba = stats.responded_existence_support_valid[key_ba]
        re_support_ba = ratio(re_valid_traces_ba, trace_count)
        re_conf_ba = ratio(
            stats.responded_existence_valid[key_ba],
            count_b,
            default=1.0,
        )
        re_passed_ba = passes_thresholds(
            re_support_ba,
            re_conf_ba,
            min_support,
            min_confidence,
        )

        if re_passed_ba:
            add_rule(
                extracted_rules,
                RespondedExistenceRule(b, a),
                stats,
                re_valid_traces_ba,
                re_support_ba,
                re_conf_ba,
            )

        # RespondedExistence(a, b)
        #     -> Response(a, b)
        #         -> ChainResponse(a, b)

        if re_passed_ab:
            response_valid_traces_ab = stats.response_support_valid[key_ab]
            response_support_ab = ratio(
                response_valid_traces_ab,
                trace_count,
            )
            response_conf_ab = ratio(
                stats.response_valid[key_ab],
                count_a,
                default=1.0,
            )
            response_passed_ab = passes_thresholds(
                response_support_ab,
                response_conf_ab,
                min_support,
                min_confidence,
            )

            if response_passed_ab:
                add_rule(
                    extracted_rules,
                    ResponseRule(a, b),
                    stats,
                    response_valid_traces_ab,
                    response_support_ab,
                    response_conf_ab,
                )

                if chain_rules:
                    chain_valid_traces_ab = stats.chain_response_support_valid[key_ab]
                    chain_support_ab = ratio(
                        chain_valid_traces_ab,
                        trace_count,
                    )
                    chain_conf_ab = ratio(
                        stats.chain_response_valid[key_ab],
                        count_a,
                        default=1.0,
                    )

                    if passes_thresholds(
                        chain_support_ab,
                        chain_conf_ab,
                        min_support,
                        min_confidence,
                    ):
                        add_rule(
                            extracted_rules,
                            ChainResponseRule(a, b),
                            stats,
                            chain_valid_traces_ab,
                            chain_support_ab,
                            chain_conf_ab,
                        )

        if re_passed_ba:
            response_valid_traces_ba = stats.response_support_valid[key_ba]
            response_support_ba = ratio(
                response_valid_traces_ba,
                trace_count,
            )
            response_conf_ba = ratio(
                stats.response_valid[key_ba],
                count_b,
                default=1.0,
            )
            response_passed_ba = passes_thresholds(
                response_support_ba,
                response_conf_ba,
                min_support,
                min_confidence,
            )

            if response_passed_ba:
                add_rule(
                    extracted_rules,
                    ResponseRule(b, a),
                    stats,
                    response_valid_traces_ba,
                    response_support_ba,
                    response_conf_ba,
                )

                if chain_rules:
                    chain_valid_traces_ba = stats.chain_response_support_valid[key_ba]
                    chain_support_ba = ratio(
                        chain_valid_traces_ba,
                        trace_count,
                    )
                    chain_conf_ba = ratio(
                        stats.chain_response_valid[key_ba],
                        count_b,
                        default=1.0,
                    )

                    if passes_thresholds(
                        chain_support_ba,
                        chain_conf_ba,
                        min_support,
                        min_confidence,
                    ):
                        add_rule(
                            extracted_rules,
                            ChainResponseRule(b, a),
                            stats,
                            chain_valid_traces_ba,
                            chain_support_ba,
                            chain_conf_ba,
                        )

        # Precedence(a, b) <--- RespondedExistence(b, a).
        # Precedence(b, a) <--- RespondedExistence(a, b).

        if re_passed_ba:
            precedence_valid_traces_ab = stats.precedence_support_valid[key_ab]
            precedence_support_ab = ratio(
                precedence_valid_traces_ab,
                trace_count,
            )
            precedence_conf_ab = ratio(
                stats.precedence_valid[key_ab],
                count_b,
                default=1.0,
            )
            precedence_passed_ab = passes_thresholds(
                precedence_support_ab,
                precedence_conf_ab,
                min_support,
                min_confidence,
            )

            if precedence_passed_ab:
                add_rule(
                    extracted_rules,
                    PrecedenceRule(a, b),
                    stats,
                    precedence_valid_traces_ab,
                    precedence_support_ab,
                    precedence_conf_ab,
                )

                if chain_rules:
                    chain_prec_valid_traces_ab = stats.chain_precedence_support_valid[
                        key_ab
                    ]
                    chain_prec_support_ab = ratio(
                        chain_prec_valid_traces_ab,
                        trace_count,
                    )
                    chain_prec_conf_ab = ratio(
                        stats.chain_precedence_valid[key_ab],
                        count_b,
                        default=1.0,
                    )

                    if passes_thresholds(
                        chain_prec_support_ab,
                        chain_prec_conf_ab,
                        min_support,
                        min_confidence,
                    ):
                        add_rule(
                            extracted_rules,
                            ChainPrecedenceRule(a, b),
                            stats,
                            chain_prec_valid_traces_ab,
                            chain_prec_support_ab,
                            chain_prec_conf_ab,
                        )

        if re_passed_ab:
            precedence_valid_traces_ba = stats.precedence_support_valid[key_ba]
            precedence_support_ba = ratio(
                precedence_valid_traces_ba,
                trace_count,
            )
            precedence_conf_ba = ratio(
                stats.precedence_valid[key_ba],
                count_a,
                default=1.0,
            )
            precedence_passed_ba = passes_thresholds(
                precedence_support_ba,
                precedence_conf_ba,
                min_support,
                min_confidence,
            )

            if precedence_passed_ba:
                add_rule(
                    extracted_rules,
                    PrecedenceRule(b, a),
                    stats,
                    precedence_valid_traces_ba,
                    precedence_support_ba,
                    precedence_conf_ba,
                )

                if chain_rules:
                    chain_prec_valid_traces_ba = stats.chain_precedence_support_valid[
                        key_ba
                    ]
                    chain_prec_support_ba = ratio(
                        chain_prec_valid_traces_ba,
                        trace_count,
                    )
                    chain_prec_conf_ba = ratio(
                        stats.chain_precedence_valid[key_ba],
                        count_a,
                        default=1.0,
                    )

                    if passes_thresholds(
                        chain_prec_support_ba,
                        chain_prec_conf_ba,
                        min_support,
                        min_confidence,
                    ):
                        add_rule(
                            extracted_rules,
                            ChainPrecedenceRule(b, a),
                            stats,
                            chain_prec_valid_traces_ba,
                            chain_prec_support_ba,
                            chain_prec_conf_ba,
                        )

        # NotSuccession

        not_succ_valid_traces_ab = stats.not_succession_support_valid[key_ab]
        not_succ_support_ab = ratio(
            not_succ_valid_traces_ab,
            trace_count,
        )
        not_succ_conf_ab = ratio(
            stats.not_succession_valid[key_ab],
            count_a,
            default=0.0,
        )

        if passes_thresholds(
            not_succ_support_ab,
            not_succ_conf_ab,
            min_support,
            min_confidence,
        ):
            add_rule(
                extracted_rules,
                NotSuccessionRule(a, b),
                stats,
                not_succ_valid_traces_ab,
                not_succ_support_ab,
                not_succ_conf_ab,
            )

        not_succ_valid_traces_ba = stats.not_succession_support_valid[key_ba]
        not_succ_support_ba = ratio(
            not_succ_valid_traces_ba,
            trace_count,
        )
        not_succ_conf_ba = ratio(
            stats.not_succession_valid[key_ba],
            count_b,
            default=0.0,
        )

        if passes_thresholds(
            not_succ_support_ba,
            not_succ_conf_ba,
            min_support,
            min_confidence,
        ):
            add_rule(
                extracted_rules,
                NotSuccessionRule(b, a),
                stats,
                not_succ_valid_traces_ba,
                not_succ_support_ba,
                not_succ_conf_ba,
            )

        both = stats.co_existence_count[frozenset((a, b))]

        neither = trace_count - count_a - count_b + both
        coexist_valid_traces = both + neither

        coexist_support = ratio(
            coexist_valid_traces,
            trace_count,
        )

        coexist_activated = count_a + count_b - both
        coexist_conf = ratio(
            both,
            coexist_activated,
            default=1.0,
        )

        if passes_thresholds(
            coexist_support,
            coexist_conf,
            min_support,
            min_confidence,
        ):
            add_rule(
                extracted_rules,
                CoExistenceRule(a, b),
                stats,
                coexist_valid_traces,
                coexist_support,
                coexist_conf,
            )

        # NotCoExistence can only pass support if both directional
        # NotSuccession roots meet the support threshold.
        if not_succ_support_ab >= min_support and not_succ_support_ba >= min_support:
            not_coexist_valid_traces = trace_count - both
            not_coexist_support = ratio(
                not_coexist_valid_traces,
                trace_count,
            )

            not_coexist_conf = ratio(
                count_a + count_b - both,
                count_a + count_b,
                default=0.0,
            )

            if passes_thresholds(
                not_coexist_support,
                not_coexist_conf,
                min_support,
                min_confidence,
            ):
                add_rule(
                    extracted_rules,
                    NotCoExistenceRule(a, b),
                    stats,
                    not_coexist_valid_traces,
                    not_coexist_support,
                    not_coexist_conf,
                )

    reduced = reduce_rule_hierarchies(extracted_rules)
    return minimize_rule_set(reduced, log)


if __name__ == "__main__":
    dataset = [
        ["A", "B", "C", "D", "A"],
        ["E", "F", "G"],
        ["A", "C", "E", "A"],
        ["B", "D", "F"],
    ]

    rules = extract(
        dataset,
        min_support=0.36,
        min_confidence=0.16,
    )

    print(f"After extraction/reduction: {len(rules)} rules")
