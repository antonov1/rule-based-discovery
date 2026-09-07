from typing import Callable, List, Union

import pandas as pd
import pm4py
from inductive_miner.cuts.concurrent_cut import ConcurrentCut
from inductive_miner.cuts.exclusive import ExclusiveChoiceCut
from inductive_miner.cuts.loop_cut import LoopCut
from inductive_miner.cuts.strict_sequence import StrictSequenceCut
from inductive_miner.fallthroughs import (
    activity_concur,
    activity_once,
    empty,
    empty,
    flower_model,
    n_tau,
    po,
    s_tau,
    xor,
)
from inductive_miner.im_utils import (
    add_child,
    base_cases,
    normalize_tree,
    repair_mechanism,
)
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules.rule_utils import preprocess_rule_set
from rules import *

from inductive_miner.im_utils import Decomposition, RepairVariant
from metrics.fitness import fitness_alignment
from metrics.precision import precision_alignments_ebi_rust
from metrics.rule_conformance import conformance as rule_conformance_apply
from utils.directly_follows_graph import DirectlyFollowsGraph

ENABLE_PRINTS = True


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def traces_to_log(
    traces,
    activity_key="concept:name",
    case_key="case:concept:name",
    timestamp_key="time:timestamp",
):
    start_time = "2024-01-01 00:00:00"
    freq = "1min"
    rows = []
    current_time = pd.Timestamp(start_time)
    for case_id, trace in enumerate(traces):
        for activity in trace:
            rows.append(
                {case_key: case_id, activity_key: activity, timestamp_key: current_time}
            )
            current_time += pd.Timedelta(freq)
    df = pd.DataFrame(rows)
    df[case_key] = df[case_key].astype(str)
    df[activity_key] = df[activity_key].astype(str)
    df[timestamp_key] = pd.to_datetime(df[timestamp_key])
    return df


def filter_log_by_rules(log, rules):
    filtered_log = log

    for rule in rules:
        filtered_log = rule.apply(filtered_log)

    return filtered_log


def mine_decomposition(
    decomposition: Decomposition,
    im_function: Callable,
    repair_mode=None,
    noise_threshold=None,
    **kwargs,
):
    parent = ProcessTree(operator=decomposition.operator)

    for i, sublog in enumerate(decomposition.sublogs):
        subrules = (
            decomposition.projected_rules[i]
            if decomposition.projected_rules is not None
            else None
        )

        kwargs = {}

        if repair_mode is not None:
            kwargs["repair_mode"] = repair_mode

        if noise_threshold is not None:
            kwargs["noise_threshold"] = noise_threshold

        if subrules is not None:
            child = im_function(
                sublog,
                subrules,
                **kwargs,
            )
        else:
            child = im_function(
                sublog,
                **kwargs,
            )

        add_child(parent, child)

    return parent


def preprocess_and_apply_IM_with_rules(
    log: Union[pd.DataFrame, List],
    rules: List[AbstractRule] = [],
    activity_key="concept:name",
    case_key="case:concept:name",
    repair_mode=RepairVariant.EventLevel,
    noise_threshold: float = 0,
):
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(log)
    rules, log = preprocess_rule_set(rules, log)
    {e for trace in log for e in trace}
    return apply_IM_with_rules(
        log=log, rules=rules, repair_mode=repair_mode, noise_threshold=noise_threshold
    )


def apply_IM_with_rules(
    log: Union[pd.DataFrame, List],
    rules: List[AbstractRule] = [],
    activity_key="concept:name",
    case_key="case:concept:name",
    repair_mode=RepairVariant.EventLevel,
    noise_threshold: float = 0,
):
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    process_tree = ProcessTree()
    rules = rules or []

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph
    dfg_graph = (
        DirectlyFollowsGraph.filter(threshold=noise_threshold, dfg=dfg_graph)
        if noise_threshold > 0
        else dfg_graph
    )
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]

    applicable_but_rejected_cuts = []
    # --- EMPTY TRACES --- #
    empty_traces = (
        empty(log=log, rules=rules) if "ArtificialNoneNode" in dfg_graph else None
    )
    if isinstance(empty_traces, set):
        applicable_but_rejected_cuts.append(
            {
                "cut": empty,
                "unsat_rules": empty_traces,
            }
        )
    elif isinstance(empty_traces, Decomposition):
        return mine_decomposition(
            decomposition=empty_traces,
            im_function=apply_IM_with_rules,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )
    # --- END OF EMPTY TRACES --- #

    # --- BASE CASE --- #

    if len(dfg_graph.nodes) <= 1 or (
        len(dfg_graph.nodes) == 2 and "ArtificialNoneNode" in dfg_graph
    ):
        process_tree = base_cases(
            log=log,
            process_tree=process_tree,
            dfg_graph=dfg_graph,
            rules=rules,
        )

        if isinstance(process_tree, set):
            applicable_but_rejected_cuts.append(
                {
                    "cut": base_cases,
                    "unsat_rules": process_tree,
                }
            )
        else:
            return process_tree
    # --- END OF BASE CASE --- #

    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if ENABLE_PRINTS:
            print(f"Cut {op} discovered with groups {groups} and rules: {rules}")
            print(f"Groups are: {groups}")

        if groups is not None:
            unsat_rules = cut.check_rules(rules, groups)
            if unsat_rules:
                applicable_but_rejected_cuts.append(
                    {
                        "cut": cut_class,
                        "unsat_rules": unsat_rules,
                    }
                )
                continue
            else:
                sublogs = cut.project(log, groups)
                projected_rules = cut.project_rules(rules, groups) if rules else None
                decomposition = Decomposition(
                    operator=op, sublogs=sublogs, projected_rules=projected_rules
                )
                if ENABLE_PRINTS:
                    alphabet = set([act for trace in log for act in trace])
                    print("***")
                    print("ACTS:", sorted(alphabet))
                    print("RULES:", [str(r) for r in rules])
                    print("OP:", op)
                    print("GROUPS:", [sorted(g) for g in groups])
                    print(
                        "PROJECTED RULES:",
                        (
                            [proj_group for proj_group in projected_rules]
                            if projected_rules
                            else None
                        ),
                    )
                    print(
                        "SUBLOGS:",
                        [
                            {
                                "acts": sorted(set(a for t in sl for a in t)),
                                "n_traces": len(sl),
                                "n_empty": sum(1 for t in sl if len(t) == 0),
                            }
                            for sl in sublogs
                        ],
                    )
                    print("SOURCE:", "cut")
                    print("***")

                return mine_decomposition(
                    decomposition=decomposition,
                    im_function=apply_IM_with_rules,
                    repair_mode=repair_mode,
                    noise_threshold=noise_threshold,
                )
    start_activities = dfg.start_activities
    end_activities = dfg.end_activities
    order_of_fall_throughs = [
        activity_once,
        activity_concur,
        s_tau,
        n_tau,
    ]
    name_of_fall_throughs = [
        "once",
        "concur",
        "s_tau",
        "tau",
    ]
    for idx, fallthrough in enumerate(order_of_fall_throughs):
        # print(f"Trying to apply: {name_of_fall_throughs[idx]}")
        result = fallthrough(
            dfg=dfg_graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            rules=rules,
        )
        if isinstance(result, set):
            applicable_but_rejected_cuts.append(
                {
                    "cut": fallthrough,
                    "unsat_rules": result,
                }
            )
        elif isinstance(result, Decomposition):
            if ENABLE_PRINTS:
                print("---")
                print("APPLIED FALLTHROUGH:", name_of_fall_throughs[idx])
                print("result", result.operator)
                print("projected rules", result.projected_rules)

                print("---")

            return mine_decomposition(
                decomposition=result,
                im_function=apply_IM_with_rules,
                repair_mode=repair_mode,
                noise_threshold=noise_threshold,
            )
    # --- END OF DATA-BASED FALL-THROUGHS --- #
    # Check if any applicable but rejected cuts exist, if so, return the first one
    # --- ATTEMPT REPAIR --- #
    if applicable_but_rejected_cuts:
        # trigger the repair mechanism
        _, unsat_rules = (
            applicable_but_rejected_cuts[0]["cut"],
            applicable_but_rejected_cuts[0]["unsat_rules"],
        )
        repair = repair_mechanism(
            log,
            unsat_rules,
            original_rules=rules,
            repair_mode=repair_mode,
        )
        if repair is not None:
            print("BEFORE REPAIR:", [str(r) for r in rules])
            print("UNSAT TRIGGER:", [str(r) for r in unsat_rules])
            repaired_log, new_rules = repair
            print("AFTER REPAIR:", [str(r) for r in new_rules])
            return apply_IM_with_rules(
                log=repaired_log,
                rules=new_rules,
                repair_mode=repair_mode,
                noise_threshold=noise_threshold,
            )

    # --- RULE-BASED FALL-THROUGH --- #
    name_of_fall_throughs = ["po", "xor"]
    order_of_fall_throughs = [po, xor]
    for idx, fallthrough in enumerate(order_of_fall_throughs):
        # print(f"Trying to apply: {name_of_fall_throughs[idx]}")
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_IM_with_rules,
            rules=rules,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )
        if res:
            res.parent = process_tree.parent
            return res

    flower = flower_model(log, rules=rules)

    if flower is None:
        # Kept only for naive repair mechanism
        return ProcessTree()

    return mine_decomposition(
        decomposition=flower,
        im_function=apply_IM_with_rules,
        repair_mode=repair_mode,
        noise_threshold=noise_threshold,
    )


def apply_IM(
    log: Union[pd.DataFrame, List],
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(
            log,
            activity_key=activity_key,
            case_key=case_key,
        )

    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    cut_classes = [
        ExclusiveChoiceCut,
        StrictSequenceCut,
        ConcurrentCut,
        LoopCut,
    ]

    ops = [
        Operator.XOR,
        Operator.SEQUENCE,
        Operator.PARALLEL,
        Operator.LOOP,
    ]

    # ------------------------------------------------------------
    # EMPTY TRACES
    # ------------------------------------------------------------

    empty_result = (
        empty(
            log=log,
            rules=[],
        )
        if "ArtificialNoneNode" in dfg_graph
        else None
    )

    if isinstance(empty_result, Decomposition):
        return mine_decomposition(
            decomposition=empty_result,
            im_function=apply_IM,
        )

    # ------------------------------------------------------------
    # BASE CASES
    # ------------------------------------------------------------

    if len(dfg_graph.nodes) <= 1 or (
        len(dfg_graph.nodes) == 2 and "ArtificialNoneNode" in dfg_graph
    ):
        process_tree = base_cases(
            log=log,
            process_tree=process_tree,
            dfg_graph=dfg_graph,
            rules=[],
        )

        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        return process_tree

    # ------------------------------------------------------------
    # CUTS
    # ------------------------------------------------------------

    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()

        if ENABLE_PRINTS:
            print(f"Cut {op} discovered with groups {groups}")
            print(f"Groups are: {groups}")

        if groups is None:
            continue

        sublogs = cut.project(
            log,
            groups,
            activity_key=activity_key,
            case_key=case_key,
        )

        decomposition = Decomposition(
            operator=op,
            sublogs=sublogs,
            projected_rules=None,
        )

        if ENABLE_PRINTS:
            alphabet = {activity for trace in log for activity in trace}

            print("***")
            print("ACTS:", sorted(alphabet))
            print("OP:", op)
            print("GROUPS:", [sorted(group) for group in groups])
            print(
                "SUBLOGS:",
                [
                    {
                        "acts": sorted(
                            {activity for trace in sublog for activity in trace}
                        ),
                        "n_traces": len(sublog),
                        "n_empty": sum(1 for trace in sublog if not trace),
                    }
                    for sublog in sublogs
                ],
            )
            print("SOURCE:", "cut")
            print("***")

        return mine_decomposition(
            decomposition=decomposition,
            im_function=apply_IM,
        )

    # ------------------------------------------------------------
    # FALL-THROUGHS
    # ------------------------------------------------------------

    start_activities = dfg.start_activities
    end_activities = dfg.end_activities

    fallthroughs = [
        ("once", activity_once),
        ("concur", activity_concur),
        ("s_tau", s_tau),
        ("tau", n_tau),
        ("flower", flower_model),
    ]

    for name, fallthrough in fallthroughs:
        result = fallthrough(
            dfg=dfg_graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            rules=[],
        )

        if not isinstance(result, Decomposition):
            continue

        if ENABLE_PRINTS:
            print("---")
            print("APPLIED FALLTHROUGH:", name)
            print("result", result.operator)
            print("projected rules", result.projected_rules)
            print("---")

        return mine_decomposition(
            decomposition=result,
            im_function=apply_IM,
        )

    return ProcessTree()


import signal


class RepairModeTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise RepairModeTimeout()


signal.signal(signal.SIGALRM, timeout_handler)

TIMEOUT_SECONDS = 30 * 60

if __name__ == "__main__":
    sepsis_log = pm4py.read_xes("./inductive_miner/sepsis.xes")
    sepsis_log = pm4py.convert_to_dataframe(sepsis_log)
    sepsis_log = preprocess_log(sepsis_log)
    activities = {activity for trace in sepsis_log for activity in trace}
    print(f"Activities in the log: {activities}")
    # ---------------------------------------------------------
    # Constraint levels
    # ---------------------------------------------------------

    structural_rules = [
        InitializationRule("ER Registration"),
        AtMostOnceRule("ER Registration"),
        AtMostOnceRule("ER Triage"),
        AtMostOnceRule("ER Sepsis Triage"),
        AtMostOnceRule("IV Liquid"),
        AtMostOnceRule("IV Antibiotics"),
        AtMostOnceRule("Admission NC"),
        AtMostOnceRule("Admission IC"),
        AtMostOnceRule("Release A"),
        AtMostOnceRule("Release B"),
        AtMostOnceRule("Release C"),
        AtMostOnceRule("Release D"),
        AtMostOnceRule("Release E"),
        NotCoExistenceRule("Release A", "Release B"),
        NotCoExistenceRule("Release A", "Release C"),
        NotCoExistenceRule("Release A", "Release D"),
        NotCoExistenceRule("Release A", "Release E"),
        NotCoExistenceRule("Release B", "Release C"),
        NotCoExistenceRule("Release B", "Release D"),
        NotCoExistenceRule("Release B", "Release E"),
        NotCoExistenceRule("Release C", "Release D"),
        NotCoExistenceRule("Release C", "Release E"),
        NotCoExistenceRule("Release D", "Release E"),
    ]

    procedural_rules = [
        ResponseRule("ER Registration", "ER Triage"),
        ResponseRule("ER Triage", "ER Sepsis Triage"),
        PrecedenceRule("ER Sepsis Triage", "IV Liquid"),
        PrecedenceRule("ER Sepsis Triage", "IV Antibiotics"),
        CoExistenceRule("IV Liquid", "IV Antibiotics"),
        PrecedenceRule("ER Sepsis Triage", "Admission NC"),
        PrecedenceRule("ER Sepsis Triage", "Admission IC"),
        NotSuccessionRule("Admission IC", "Admission NC"),
        PrecedenceRule("ER Sepsis Triage", "Release A"),
        PrecedenceRule("ER Sepsis Triage", "Release B"),
        PrecedenceRule("ER Sepsis Triage", "Release C"),
        PrecedenceRule("ER Sepsis Triage", "Release D"),
        PrecedenceRule("ER Sepsis Triage", "Release E"),
    ]

    guideline_rules = [
        ResponseRule("ER Sepsis Triage", "IV Antibiotics"),
        ResponseRule("ER Sepsis Triage", "LacticAcid"),
    ]
    rule_levels = {
        "C1_structural": structural_rules,
        "C2_procedural": structural_rules + procedural_rules,
        "C3_treatment": structural_rules + procedural_rules + guideline_rules,
    }

    repair_modes = {
        "no_repair": RepairVariant.Naive,
        "edit_distance": RepairVariant.EditDistance,
    }

    noise_thresholds = [i / 10 for i in range(0, 11)]  # 0.0 to 1.0 in steps of 0.1

    # ---------------------------------------------------------
    # Load log
    # ---------------------------------------------------------

    log = pm4py.read_xes("./inductive_miner/sepsis.xes")
    log_org = log.copy()

    log = preprocess_log(log)

    alphabet = set([activity for trace in log for activity in trace])

    # ---------------------------------------------------------
    # Inspect empirical support/confidence of all clinical rules
    # ---------------------------------------------------------

    all_rules = rule_levels["C3_treatment"]

    print("\n=== Clinical rule statistics ===")

    for rule in all_rules:
        rule.apply(log.copy())

        try:
            support = rule.calc_support(log)
        except TypeError:
            support = rule.calc_support()

        try:
            confidence = rule.calc_confidence(log)
        except TypeError:
            confidence = rule.calc_confidence()

        print(
            f"Rule: {rule}, "
            f"Support: {support:.3f}, "
            f"Confidence: {confidence:.3f}"
        )

    # ---------------------------------------------------------
    # Evaluation
    # ---------------------------------------------------------

    results = []

results = []

for level_name, rules in rule_levels.items():
    for repair_name, repair_mode in repair_modes.items():
        for noise_threshold in noise_thresholds:

            print("\n" + "=" * 80)
            print(
                f"Rules: {level_name} | "
                f"Repair: {repair_name} | "
                f"Noise: {noise_threshold}"
            )
            print("=" * 80)

            signal.alarm(TIMEOUT_SECONDS)

            try:
                model = apply_IM_with_rules(
                    log=log.copy(),
                    rules=rules,
                    repair_mode=repair_mode,
                    noise_threshold=noise_threshold,
                )

                model = normalize_tree(model)

                print(f"Final model: {model}")

                fitness = fitness_alignment(log_org, model)
                precision = precision_alignments_ebi_rust(log_org, model)

                f1 = (
                    2 * fitness * precision / (fitness + precision)
                    if fitness + precision > 0
                    else 0.0
                )

                rule_conf = rule_conformance_apply(
                    model,
                    rules,
                    alphabet=alphabet,
                )[0]

                results.append(
                    {
                        "constraint_level": level_name,
                        "num_rules": len(rules),
                        "repair": repair_name,
                        "noise_threshold": noise_threshold,
                        "fitness": fitness,
                        "precision": precision,
                        "f1": f1,
                        "rule_conformance": rule_conf,
                        "model": str(model),
                        "status": "completed",
                    }
                )

                print(
                    f"Fitness: {fitness:.3f}, "
                    f"Precision: {precision:.3f}, "
                    f"F1: {f1:.3f}, "
                    f"Rule Conf: {rule_conf:.3f}"
                )

            except RepairModeTimeout:
                print(
                    f"TIMEOUT after 30 min: "
                    f"{level_name} | {repair_name} | "
                    f"noise={noise_threshold:.2f}"
                )

                results.append(
                    {
                        "constraint_level": level_name,
                        "num_rules": len(rules),
                        "repair": repair_name,
                        "noise_threshold": noise_threshold,
                        "fitness": None,
                        "precision": None,
                        "f1": None,
                        "rule_conformance": None,
                        "model": None,
                        "status": "timeout",
                    }
                )

            finally:
                signal.alarm(0)
    # ---------------------------------------------------------
    # Compact summary
    # ---------------------------------------------------------

    print("\n\n=== SUMMARY ===")

    for result in results:
        if result.get("status") == "completed":
            print(
                f"{result['constraint_level']:15s} | "
                f"{result['repair']:13s} | "
                f"noise={result['noise_threshold']:.2f} | "
                f"fit={result['fitness']:.3f} | "
                f"prec={result['precision']:.3f} | "
                f"F1={result['f1']:.3f} | "
                f"RC={result['rule_conformance']:.3f} | "
                f"status=completed"
            )
        else:
            print(
                f"{result['constraint_level']:15s} | "
                f"{result['repair']:13s} | "
                f"noise={result['noise_threshold']:.2f} | "
                f"status={result.get('status', 'unknown')}"
            )

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        "./inductive_miner/results_sepsis.csv",
        index=False,
    )
