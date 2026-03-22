from typing import List, Union

import pandas as pd
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
    s_tau,
)
from inductive_miner.im_utils import add_child, base_cases
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from utils.directly_follows_graph import DirectlyFollowsGraph

ENABLE_PRINTS = False


def handle_empty_traces(log, im_function):
    if any(len(trace) == 0 for trace in log):
        # Remove empty traces from the log
        non_empty_log = [t for t in log if len(t) > 0]
        if not non_empty_log:
            return ProcessTree()  # Pure Tau

        # Recursively mine the non-empty part and wrap in XOR
        subtree = im_function(non_empty_log)
        root = ProcessTree(operator=Operator.XOR)
        add_child(root, ProcessTree())  # Add Tau
        add_child(root, subtree)  # Add the actual process
        return root
    return None


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


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
        parent = process_tree.parent
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        process_tree.parent = parent
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
