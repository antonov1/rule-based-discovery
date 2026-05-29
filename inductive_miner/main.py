from typing import List, Union

import pandas as pd
import pm4py
from inductive_miner.cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from inductive_miner.cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from inductive_miner.cuts.loop_cut import BinaryLoopCut, LoopCut
from inductive_miner.cuts.strict_sequence import (
    BinaryStrictSequenceCut,
    StrictSequenceCut,
)
from inductive_miner.fallthroughs import (
    activity_concur,
    activity_once,
    empty,
    flower_model,
    n_tau,
    rule_seq,
    s_tau,
)
from inductive_miner.im_utils import (
    add_child,
    assert_rules_supported,
    base_cases,
    intersection_of_logs,
    repair_mechanism,
)
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import *
from inductive_miner.im_utils import RepairVariant
from metrics.fitness import fitness_token_based_tree
from metrics.precision import precision_token_based_tree
from metrics.rule_conformance import (
    conformance as rule_conformance_apply,
    weighted_conformance as weighted_rule_conformance_apply,
)
from utils.directly_follows_graph import DirectlyFollowsGraph

ENABLE_PRINTS = False


def handle_empty_traces(
    log,
    im_function,
    rules: List[AbstractRule] = None,
    repair_mode=RepairVariant.TraceLevel,
):
    if any(len(trace) == 0 for trace in log):
        # Remove empty traces from the log
        non_empty_log = [t for t in log if len(t) > 0]

        if rules:
            act_set = set([act for trace in log for act in trace])
            groups = [set(), act_set]
            unsat_rules = ExclusiveChoiceCut.check_rules(rules, groups)
            if unsat_rules:
                return repair_mechanism(
                    log, unsat_rules, im_function, rules, repair_mode
                )

        if not non_empty_log:
            return ProcessTree()  # Pure Tau

        # Recursively mine the non-empty part and wrap in XOR

        subtree = (
            im_function(non_empty_log, rules)
            if rules is not None
            else im_function(non_empty_log)
        )
        root = ProcessTree(operator=Operator.XOR)
        add_child(root, ProcessTree())  # Add Tau
        add_child(root, subtree)  # Add the actual process
        return root
    return None


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


def apply_BIM_with_rules(
    log: Union[pd.DataFrame, List],
    rules: List[AbstractRule] = [],
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if isinstance(log, pd.DataFrame):
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    act_in_log = set([e for trace in log for e in trace])

    if rules:
        intersection_logs = [r.apply(log) for r in rules]
        intersection_logs = intersection_of_logs(intersection_logs)
        if len(intersection_logs) == 0:
            act_in_log = set([e for trace in log for e in trace])

            raise Exception(
                f"The support of the rules {rules} is 0. Activities are {act_in_log}."
            )
    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    # Try to apply the cuts in order of precedence
    cut_classes = [
        BinaryExclusiveChoiceCut,
        BinaryStrictSequenceCut,
        BinaryConcurrentCut,
        BinaryLoopCut,
    ]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    empty_traces = handle_empty_traces(log, apply_IM_with_rules, rules=rules)
    # print(f"Log is: {log}")
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log,
            process_tree,
            dfg_graph,
            apply_IM_with_rules,
            rules,
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        return process_tree
    log_act_set = set([act for trace in log for act in trace])
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if ENABLE_PRINTS:
            print(f"Cut {op} discovered with groups {groups}")
        if groups is not None:
            if ENABLE_PRINTS:
                print(f"Groups are: {groups}")
            unsat_rules = cut.check_rules(rules, groups)
            if unsat_rules:

                repaired_log = repair_mechanism(
                    log, unsat_rules, apply_BIM_with_rules, rules
                )
                if ENABLE_PRINTS:
                    print(
                        f"Unsat rules for {op} with groups {groups}: {[str(r) for r in unsat_rules]}, Repaired via: {repaired_log}"
                    )

                if repaired_log:
                    return repaired_log
                else:
                    continue

            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )
            projected_rules = cut.project_rules(rules, groups)
            for i in range(len(sublogs)):
                assert_rules_supported(
                    "In rule refinement:", sublogs[i], projected_rules[i]
                )

                child_node = apply_BIM_with_rules(
                    sublogs[i],
                    projected_rules[i],
                    activity_key=activity_key,
                    case_key=case_key,
                )
                add_child(process_tree, child_node)
            if ENABLE_PRINTS:
                print("***")
                print("ACTS:", sorted(log_act_set))
                print("RULES:", [str(r) for r in rules])
                print("OP:", op)
                print("GROUPS:", [sorted(g) for g in groups])
                print(
                    "PROJECTED RULES:", [proj_group for proj_group in projected_rules]
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
            return process_tree
    start_activities = dfg.start_activities
    end_activities = dfg.end_activities
    order_of_fall_throughs = [
        empty,
        activity_once,
        activity_concur,
        s_tau,
        n_tau,
        flower_model,
        rule_seq,
    ]
    name_of_fall_throughs = [
        "empty",
        "once",
        "concur",
        "s_tau",
        "tau",
        "flower",
        "rseq",
    ]
    for idx, fallthrough in enumerate(order_of_fall_throughs):
        # print(f"Trying to apply: {name_of_fall_throughs[idx]}")
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_BIM_with_rules,
            rules=rules,
        )
        if res:
            if ENABLE_PRINTS:
                print("---")
                print("APPLIED FALLTHROUGH:", name_of_fall_throughs[idx])
                print("result", res)

                print("---")

            res.parent = process_tree.parent
            return res
    return ProcessTree()


def filter_log_by_rules(log, rules):
    filtered_log = log

    for rule in rules:
        filtered_log = rule.apply(filtered_log)

    return filtered_log


def apply_IM_with_rules(
    log: Union[pd.DataFrame, List],
    rules: List[AbstractRule] = [],
    activity_key="concept:name",
    case_key="case:concept:name",
    repair_mode=RepairVariant.TraceLevel,
):
    # print(f"Rules are: {rules}")
    # print(f"Log is: {log}")
    # First, we can apply the rules to filter the log
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    # Check if the support of rule combos is bigger than 0, if not, raise Exception
    act_in_log = set([e for trace in log for e in trace])

    if rules:
        filtered_log = filter_log_by_rules(log, rules)
        # print(f"The filtered log is: {filtered_log}")
        if len(filtered_log) == 0:
            act_in_log = set([e for trace in log for e in trace])
            # export the log

            raise Exception(
                f"The support of the rules {rules} is 0. Activities are {act_in_log}."
            )
    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces

    empty_traces = handle_empty_traces(
        log,
        apply_IM_with_rules,
        rules=rules,
        repair_mode=repair_mode,
    )
    # print(f"Log is: {log}")
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log,
            process_tree,
            dfg_graph,
            apply_IM_with_rules,
            rules,
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        return process_tree
    log_act_set = set([act for trace in log for act in trace])
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if ENABLE_PRINTS:
            print(f"Cut {op} discovered with groups {groups}")
        if groups is not None:
            if ENABLE_PRINTS:
                print(f"Groups are: {groups}")
            unsat_rules = cut.check_rules(rules, groups)
            if unsat_rules:

                repaired_log = repair_mechanism(
                    log,
                    unsat_rules,
                    apply_IM_with_rules,
                    rules,
                    repair_mode,
                )
                if ENABLE_PRINTS:
                    print(
                        f"Unsat rules for {op} with groups {groups}: {[str(r) for r in unsat_rules]}, Repaired via: {repaired_log}"
                    )

                if repaired_log:
                    return repaired_log
                else:
                    continue

            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )
            projected_rules = cut.project_rules(rules, groups)
            for i in range(len(sublogs)):
                assert_rules_supported(
                    "In rule refinement:", sublogs[i], projected_rules[i]
                )

                child_node = apply_IM_with_rules(
                    sublogs[i],
                    projected_rules[i],
                    activity_key=activity_key,
                    case_key=case_key,
                    repair_mode=repair_mode,
                )
                add_child(process_tree, child_node)
            if ENABLE_PRINTS:
                print("***")
                print("ACTS:", sorted(log_act_set))
                print("RULES:", [str(r) for r in rules])
                print("OP:", op)
                print("GROUPS:", [sorted(g) for g in groups])
                print(
                    "PROJECTED RULES:", [proj_group for proj_group in projected_rules]
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
            return process_tree
    start_activities = dfg.start_activities
    end_activities = dfg.end_activities
    order_of_fall_throughs = [
        empty,
        activity_once,
        activity_concur,
        s_tau,
        n_tau,
        flower_model,
        rule_seq,
    ]
    name_of_fall_throughs = [
        "empty",
        "once",
        "concur",
        "s_tau",
        "tau",
        "flower",
        "rseq",
    ]
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
        )
        if res:
            if ENABLE_PRINTS:
                print("---")
                print("APPLIED FALLTHROUGH:", name_of_fall_throughs[idx])
                print("result", res)

                print("---")

            res.parent = process_tree.parent
            return res
    return ProcessTree()


def apply_IM(
    log: Union[pd.DataFrame, List],
    activity_key="concept:name",
    case_key="case:concept:name",
):

    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    log_act_set = set([act for trace in log for act in trace])
    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    empty_traces = handle_empty_traces(log, apply_IM)
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        return process_tree

    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:
            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )
            for sublog in sublogs:
                child_node = apply_IM(
                    sublog, activity_key=activity_key, case_key=case_key
                )
                add_child(process_tree, child_node)
            if ENABLE_PRINTS:
                print("***")
                print("ACTS:", sorted(log_act_set))
                print("OP:", op)
                print("GROUPS:", [sorted(g) for g in groups])
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
            return process_tree
    start_activities = dfg.start_activities
    end_activities = dfg.end_activities
    order_of_fall_throughs = [
        empty,
        activity_once,
        activity_concur,
        s_tau,
        n_tau,
        flower_model,
    ]
    name_of_fall_throughs = ["empty", "once", "concur", "s_tau", "tau", "flower"]
    for idx, fallthrough in enumerate(order_of_fall_throughs):
        # print(f"Trying to apply: {name_of_fall_throughs[idx]}")
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_IM,
        )
        if res:
            if ENABLE_PRINTS:
                print("---")
                print("ACTS:", sorted(log_act_set))
                print("FALLTHROUGH:", name_of_fall_throughs[idx])
                print("---")

            res.parent = process_tree.parent
            return res
    return ProcessTree()


def apply_binary_IM(
    log: Union[pd.DataFrame, List],
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)
    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    empty_traces = handle_empty_traces(log, apply_IM)
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        parent = process_tree.parent
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )

        process_tree.parent = parent
        return process_tree

    # Try to apply the cuts in order of precedence

    cut_classes = [
        BinaryExclusiveChoiceCut,
        BinaryStrictSequenceCut,
        BinaryConcurrentCut,
        BinaryLoopCut,
    ]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]

    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:
            parent = process_tree.parent
            process_tree = ProcessTree(operator=op)
            process_tree.parent = parent
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )

            for i in range(len(sublogs)):
                child_node = apply_binary_IM(
                    sublogs[i],
                    activity_key=activity_key,
                    case_key=case_key,
                )
                add_child(process_tree, child_node)

            return process_tree
    # Now, we can apply the fall-throughs because no cut was detected
    start_activities = dfg.start_activities
    end_activities = dfg.end_activities
    order_of_fall_throughs = [
        empty,
        activity_once,
        activity_concur,
        s_tau,
        n_tau,
        flower_model,
    ]
    for _, fallthrough in enumerate(order_of_fall_throughs):
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_binary_IM,
            binary=True,
        )
        if res:
            res.parent = process_tree.parent
            return res
    return ProcessTree()


if __name__ == "__main__":
    """

        example_log = [["B", "A", "B", "A", "B"], ["B"]]
        org = apply_IM(example_log)
        print(f"ORG: {org}")

        rules = [ExistenceRule("A")]
        print(apply_IM_with_rules(example_log, rules=rules))

        bpic = pm4py.read_xes("./inductive_miner/BPIC2017.xes")
        bpic_log = pm4py.convert_to_dataframe(bpic)
        # rules = [ExistenceRule("O_CANCELLED"]), ExistenceRule("A_APPROVED"])]

        rules = [
            ResponseRule("A_DECLINED", "W_Completeren aanvraag"),
            PrecedenceRule("A_ACCEPTED", "A_DECLINED"),
            ExistenceRule("A_DECLINED"),
        ]

        rules = [
            ExistenceRule("A_Denied"),
            ResponseRule("A_Denied", "W_Complete application"),
        ]
        # rules = [ExistenceRule("A_FINALIZED"])]

        rules = [
            AtMostOnceRule("O_Create Offer"),
            PrecedenceRule("O_Accepted", "A_Pending"),
        ]

        # rules = [NotSuccessionRule("O_Create Offer", "W_Call after offers"])]
        model = normalize_tree(apply_BIM_with_rules(bpic_log, rules))
        net, im, fm = pm4py.convert_to_petri_net(model)
        net, im, fm = pm4py.reduce_petri_net_implicit_places(net, im, fm)
        print(f"(BIM) Model is: {model}")
        model = normalize_tree(apply_IM_with_rules(bpic_log, rules))
        print(f"Model is: {model}")
        print(rule_conformance_apply(model, rules))


        # gviz = pm4py.visualization.petri_net.visualizer.apply(net, im, fm)
        # pm4py.visualization.petri_net.visualizer.view(gviz)

        fitness = pm4py.fitness_token_based_replay(bpic_log, net, im, fm)
        print(f"Fitness: {fitness}")
        prec = pm4py.precision_token_based_replay(bpic_log, net, im, fm)
        print(f"Prec: {prec}")

        rules = [
            PrecedenceRule("ER Sepsis Triage", "IV Antibiotics"),
            CoExistenceRule("ER Sepsis Triage", "CRP"),
            ExistenceRule("ER Sepsis Triage"),
            CoExistenceRule("ER Sepsis Triage", "LacticAcid")
        ]

        Response(ER Sepsis Triage, LacticAcid)
    Response(ER Sepsis Triage, IV Antibiotics)
    Initialization(ER Registration)
    NotCoExistence(Admission NC, Release A)
    """
    rules = [
        ResponseRule("ER Sepsis Triage", "LacticAcid"),
        ResponseRule("ER Sepsis Triage", "IV Antibiotics"),
        InitializationRule("ER Registration"),
        NotCoExistenceRule("Admission NC", "Release A"),
    ]

    log = pm4py.read_xes("./inductive_miner/sepsis.xes")
    log = pm4py.convert_to_dataframe(log)
    log_org = log.copy()

    log = preprocess_log(log)
    for r in rules:
        log = r.apply(log)
    model = apply_IM(log)
    print(model)
    fitness = fitness_token_based_tree(log_org, model)
    prec = precision_token_based_tree(log_org, model)
    print(f"Fit: {fitness}, prec: {prec}")
    rule_conf = rule_conformance_apply(
        model, rules, alphabet=set(log_org["concept:name"].unique())
    )
    weighted_rule_conf = weighted_rule_conformance_apply(
        model, rules, alphabet=set(log_org["concept:name"].unique()), log=log
    )
    print(f"Rule Conf: {rule_conf}, Weighted Rule Conf : {rule_conf}")
