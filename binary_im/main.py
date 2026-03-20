from typing import List, Union

import numpy as np
import pandas as pd
from binary_im.im_utils import add_child, base_cases
from cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from cuts.loop_cut import BinaryLoopCut, LoopCut
from cuts.strict_sequence import BinaryStrictSequenceCut, StrictSequenceCut
from fallthroughs import (
    activity_concur,
    activity_once,
    empty,
    flower_model,
    n_tau,
    s_tau,
)
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from utils.directly_follows_graph import DirectlyFollowsGraph

ENABLE_PRINTS = False


def handle_empty_traces(log):
    if any(len(trace) == 0 for trace in log):
        # Remove empty traces from the log
        non_empty_log = [t for t in log if len(t) > 0]
        if not non_empty_log:
            return ProcessTree()  # Pure Tau

        # Recursively mine the non-empty part and wrap in XOR
        subtree = apply_IM(non_empty_log, ProcessTree())
        root = ProcessTree(operator=Operator.XOR)
        add_child(root, ProcessTree())  # Add Tau
        add_child(root, subtree)  # Add the actual process
        return root
    return None


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def apply_IM(
    log: Union[pd.DataFrame, List],
    process_tree: ProcessTree = None,
    activity_key="concept:name",
    case_key="case:concept:name",
    activate=False,
):

    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    empty_traces = handle_empty_traces(log)
    if empty_traces is not None:
        return empty_traces

    if process_tree is None:
        process_tree = ProcessTree()
    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    log_act_set = set([act for trace in log for act in trace])
    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    if len(dfg_graph.nodes) <= 1 or (
        len(dfg_graph.nodes) == 2 and "ArtificialNoneNode" in list(dfg_graph.nodes)
    ):
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
                    sublog,
                    ProcessTree(),
                    activity_key=activity_key,
                    case_key=case_key,
                    activate=activate,
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
    process_tree: ProcessTree = None,
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)
    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph
    if process_tree is None:
        process_tree = ProcessTree()
    # Try to apply the cuts in order of precedence
    cut_classes = [
        BinaryExclusiveChoiceCut,
        BinaryStrictSequenceCut,
        BinaryConcurrentCut,
        BinaryLoopCut,
    ]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    if len(dfg_graph.nodes) <= 1 or (
        len(dfg_graph.nodes) == 2 and "ActivityNoneNode" in list(dfg_graph.nodes)
    ):
        parent = process_tree.parent
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
        # print(f"BASE CASE TREE {process_tree}")

        process_tree.parent = parent
        return process_tree
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
                    ProcessTree(),
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
    for idx, fallthrough in enumerate(order_of_fall_throughs):
        # print(f"Trying to apply: {name_of_fall_throughs[idx]}")
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_binary_IM,
            binary=True,
        )
        # print(f"Trying fallthrough {name_of_fall_throughs[idx]} with res {res}")
        if res:
            res.parent = process_tree.parent
            return res
    return ProcessTree()


# let's test this
if __name__ == "__main__":

    import pm4py
    from pm4py.algo.discovery.inductive import algorithm as inductive_miner
    from pm4py.algo.simulation.playout.process_tree.algorithm import (
        apply as playout_process_tree,
    )
    from pm4py.algo.simulation.tree_generator.algorithm import (
        apply as simulate_process_tree,
    )
    from pm4py.objects.conversion.log import converter as log_converter
    from pm4py.objects.conversion.log.variants.df_to_event_log_1v import (
        apply as df_to_event_log,
    )

    def preprocess_log_v2(log):
        idx = 0
        time = 0
        for trace in log:
            for event in trace:
                event["case:concept:name"] = f"case_{idx}"
                event["time_timestamp"] = time
                time += 1
            idx += 1
        return log

    times_BIM = []
    times_sIM = []
    times_pm4py = []
    events = 0
    cases = 0
    similarity_to_pm4py_bim = []
    similarity_to_pm4py_sim = []

    for i in range(200):
        process_tree = simulate_process_tree()
        log = preprocess_log_v2(playout_process_tree(process_tree))
        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

        print(
            f"Log has {len(log)} events and {len(log['concept:name'].unique())} unique activities."
        )
        # apply the binary IM
        events += len(log)
        cases += len(log["case:concept:name"].unique())
        # BIM
        start_time = pd.Timestamp.now()
        model_bim = apply_IM(log)
        end_time = pd.Timestamp.now()
        times_BIM.append((end_time - start_time).total_seconds() * 1000)
        # SIM
        start_time = pd.Timestamp.now()
        model_sim = apply_IM(log)
        end_time = pd.Timestamp.now()
        times_sIM.append((end_time - start_time).total_seconds() * 1000)
        start_time = pd.Timestamp.now()
        model_pm4py = inductive_miner.apply(df_to_event_log(log))
        end_time = pd.Timestamp.now()
        times_pm4py.append((end_time - start_time).total_seconds() * 1000)
        sim_pm4py_sim = pm4py.behavioral_similarity(model_sim, model_pm4py)
        print(f"MODEL SIM: {model_sim}")
        print(f"MODEL PM4Py: {model_pm4py}")
        print(sim_pm4py_sim)

        similarity_to_pm4py_bim.append(
            pm4py.behavioral_similarity(model_bim, model_pm4py)
        )
        similarity_to_pm4py_sim.append(sim_pm4py_sim)

    # A histogram on runtimes (two boxplots)
    import matplotlib.pyplot as plt

    plt.boxplot(
        [times_BIM, times_sIM, times_pm4py],
        labels=["Binary IM", "Standard IM", "PM4Py IM"],
    )
    plt.ylabel("Runtime (ms)")
    plt.title("Runtime Comparison of Binary IM, Standard IM, and PM4Py IM")
    # a subtitle for avg trace len
    avg_trace_len = events / cases if cases > 0 else 0
    plt.suptitle(f"Average Trace Length: {avg_trace_len:.2f}", fontsize=10)
    plt.show()

    def ecdf(data):
        x = np.sort(data)
        y = np.arange(1, len(x) + 1) / len(x)
        return x, y

    x_bim, y_bim = ecdf(similarity_to_pm4py_bim)
    x_sim, y_sim = ecdf(similarity_to_pm4py_sim)

    plt.plot(x_bim, y_bim, label="BIM")
    plt.plot(x_sim, y_sim, label="SIM")

    plt.xlabel("Behavioral Similarity (comp w/ PM4Py's version)")
    plt.ylabel("Cumulative Probability")
    plt.title("ECDF of Similarity Scores")
    plt.legend()
    plt.grid(True)
    plt.show()
    """
    # import BPIC2017.xes
    log = pm4py.read_xes("./binary_im/BPIC2017.xes")
    # to a dataframe
    log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)
    print(
        f"BPIC2012 log has {len(log)} events and {len(log['concept:name'].unique())} unique activities."
    )
    start_time = pd.Timestamp.now()
    model_bim = apply_IM(log)
    end_time = pd.Timestamp.now()
    print(f"IM took {(end_time - start_time).total_seconds()} seconds on BPIC2012 log.")
    start_time = pd.Timestamp.now()
    model_pm4py = inductive_miner.apply(df_to_event_log(log))
    end_time = pd.Timestamp.now()
    print(
        f"PM4Py IM took {(end_time - start_time).total_seconds()} seconds on BPIC2012 log."
    )
    # display model_bim
    gviz = pt_visualizer.apply(model_bim)
    pt_visualizer.view(gviz)
    print(
        f"Similarity between Binary IM and PM4Py IM on BPIC2012 log: {pm4py.behavioral_similarity(model_bim, model_pm4py)}"
    )

    print(f"Process tree discovered by Binary IM on BPIC2012 log: {model_bim}")
    print(f"Process tree discovered by PM4Py IM on BPIC2012 log: {model_pm4py}")
    print(f"Similarity is {pm4py.behavioral_similarity(model_bim, model_pm4py)}")


    log1 = [
        ['W_Call incomplete files', 'A_Incomplete', 'O_Create Offer', 'O_Created'],
        ['W_Call incomplete files', 'A_Incomplete', 'O_Accepted', 'A_Pending'],
        ['W_Call incomplete files', 'O_Accepted', 'A_Pending'],
        ['W_Call incomplete files', 'A_Incomplete', 'A_Denied', 'O_Refused'],
        ['O_Returned', 'O_Accepted', 'A_Pending'],
        ['O_Returned'],
        ['W_Shortened completion '],
        ['O_Create Offer', 'O_Created'],
    ]


    model_my_miner = apply_IM(log1)
    model_pm4py = inductive_miner.apply(df_to_event_log(log1))
    print(f"Model PM4Py: {model_pm4py}")
    print(f"SIM: {model_my_miner}")
    print(f"Sim: {pm4py.behavioral_similarity(model_my_miner, model_pm4py)}")
    # Print
    """
