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


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def apply_IM(
    log: Union[pd.DataFrame, List],
    process_tree: ProcessTree = None,
    activity_key="concept:name",
    case_key="case:concept:name",
):

    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    if process_tree is None:
        process_tree = ProcessTree()
    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph
    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    if len(dfg_graph.nodes) <= 1:
        parent = process_tree.parent
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
        # print(f"BASE CASE TREE {process_tree}")

        process_tree.parent = parent
        return process_tree

    max_projections, max_op, max_size = None, None, 0
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:
            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )
            if len(sublogs) > max_size:
                max_projections = sublogs
                max_op = op
                max_size = len(sublogs)
    if max_projections and max_op:
        # print(f"We will apply {op} to {log} with sublogs {sublogs} because it has size {max_size}")
        for i in range(len(sublogs)):
            child_node = apply_IM(
                sublogs[i],
                ProcessTree(),
                activity_key=activity_key,
                case_key=case_key,
            )

            add_child(process_tree, child_node)
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
        # print(f"Trying fallthrough {name_of_fall_throughs[idx]} with res {res}")
        if res:
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
    graph_nodes = list(dfg_graph.nodes)
    # remove the artificial none node if it exists
    if "ArtificialNoneNode" in graph_nodes:
        graph_nodes.remove("ArtificialNoneNode")
    if len(graph_nodes) <= 1:
        parent = process_tree.parent
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
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
    from pm4py.visualization.process_tree import visualizer as pt_visualizer

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
    for i in range(100):
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
        model_bim = apply_binary_IM(log)
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
        similarity_to_pm4py_bim.append(
            pm4py.behavioral_similarity(model_bim, model_pm4py)
        )
        similarity_to_pm4py_sim.append(
            pm4py.behavioral_similarity(model_sim, model_pm4py)
        )

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

    plt.xlabel("Behavioral Similarity")
    plt.ylabel("Cumulative Probability")
    plt.title("ECDF of Similarity Scores")
    plt.legend()
    plt.grid(True)
    plt.show()

    # import BPIC2017.xes
    log = pm4py.read_xes("./binary_im/BPIC2017.xes")
    # to a dataframe
    log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)
    print(
        f"BPIC2017 log has {len(log)} events and {len(log['concept:name'].unique())} unique activities."
    )
    start_time = pd.Timestamp.now()
    model_bim = apply_IM(log)
    end_time = pd.Timestamp.now()
    print(f"IM took {(end_time - start_time).total_seconds()} seconds on BPIC2017 log.")
    start_time = pd.Timestamp.now()
    model_pm4py = inductive_miner.apply(df_to_event_log(log))
    end_time = pd.Timestamp.now()
    print(
        f"PM4Py IM took {(end_time - start_time).total_seconds()} seconds on BPIC2017 log."
    )
    # display model_bim
    gviz = pt_visualizer.apply(model_bim)
    pt_visualizer.view(gviz)
    print(
        f"Similarity between Binary IM and PM4Py IM on BPIC2017 log: {pm4py.behavioral_similarity(model_bim, model_pm4py)}"
    )
    print(f"Process tree discovered by Binary IM on BPIC2017 log: {model_bim}")
    print(f"Process tree discovered by PM4Py IM on BPIC2017 log: {model_pm4py}")

    """
    data = pd.DataFrame([
        # case 1
        {"case:concept:name": "c1", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c1", "concept:name": "b", "time:timestamp": 2},

        # case 2
        {"case:concept:name": "c2", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c2", "concept:name": "d", "time:timestamp": 2},

        # case 3
        {"case:concept:name": "c3", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c3", "concept:name": "e", "time:timestamp": 2},

        # case 4
        {"case:concept:name": "c4", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c4", "concept:name": "i", "time:timestamp": 2},
        {"case:concept:name": "c4", "concept:name": "a", "time:timestamp": 3},

        # case 5
        {"case:concept:name": "c5", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c5", "concept:name": "i", "time:timestamp": 2},
        {"case:concept:name": "c5", "concept:name": "o", "time:timestamp": 3},

        # case 6
        {"case:concept:name": "c6", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c6", "concept:name": "g", "time:timestamp": 2},
        {"case:concept:name": "c6", "concept:name": "h", "time:timestamp": 3},
        {"case:concept:name": "c6", "concept:name": "q", "time:timestamp": 4},

        # case 7
        {"case:concept:name": "c7", "concept:name": "c", "time:timestamp": 1},
        {"case:concept:name": "c7", "concept:name": "g", "time:timestamp": 2},
        {"case:concept:name": "c7", "concept:name": "p", "time:timestamp": 3},
        {"case:concept:name": "c7", "concept:name": "l", "time:timestamp": 4},
    ])
    log = [
        ['j', 'n', 'k'],
        ['j', 'g', 'i'],
        ['f', 'k'],
        ['b'],
        ['j'],
        ['n', 'i'],
    ]
    model_pm4py = apply_binary_IM(log)
    model_my_miner = apply_IM(log)
    print(f"IM: {model_pm4py}")
    print(f"BIM: {model_my_miner}")
    """
