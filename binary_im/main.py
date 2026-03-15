from cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from cuts.loop_cut import BinaryLoopCut, LoopCut
from cuts.sequence import BinarySequenceCut, SequenceCut
import pandas as pd
from utils.directly_follows_graph import DirectlyFollowsGraph
from pm4py.objects.process_tree.obj import ProcessTree, Operator
from binary_im.im_utils import base_cases, add_child
from typing import Union, List

def flower_model(log : pd.DataFrame, activity_key = 'concept:name', case_key = 'case:concept:name'):
    process_tree = ProcessTree(operator=Operator.PARALLEL)
    for activity in log[activity_key].unique():
        activity_node = ProcessTree(label=activity)
        activity_node.parent = process_tree
        process_tree.children.append(activity_node)
    return process_tree
def preprocess_log(log, activity_key = 'concept:name', case_key = 'case:concept:name'):
    return log.groupby(case_key)[activity_key].apply(list).tolist()
def apply_IM(log : Union[pd.DataFrame, List], process_tree : ProcessTree = None, activity_key = 'concept:name', case_key = 'case:concept:name'):

    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    if process_tree is None:
        process_tree = ProcessTree()
    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph
    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, SequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    if len(dfg_graph.nodes) <= 1:
        return base_cases(log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key)
        
        
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:
            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(log, groups, activity_key=activity_key, case_key=case_key)

            for i in range(len(sublogs)):
                child_node = apply_IM(
                        sublogs[i],
                        ProcessTree(),
                        activity_key=activity_key,
                        case_key=case_key
                )
                add_child(process_tree, child_node)
            return process_tree
    return ProcessTree()

def apply_binary_IM(log : Union[pd.DataFrame, List], process_tree : ProcessTree = None, activity_key = 'concept:name', case_key = 'case:concept:name'):
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)
    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph
    if process_tree is None:
        process_tree = ProcessTree()
    # Try to apply the cuts in order of precedence
    cut_classes = [BinaryExclusiveChoiceCut, BinarySequenceCut, BinaryConcurrentCut, BinaryLoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    graph_nodes = list(dfg_graph.nodes)
    # remove the artificial none node if it exists
    if 'ArtificialNoneNode' in graph_nodes:
        graph_nodes.remove('ArtificialNoneNode')
    if len(graph_nodes) <= 1:
        return base_cases(log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key)
        
        
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:

            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(log, groups, activity_key=activity_key, case_key=case_key)

            for i in range(len(sublogs)):
                child_node = apply_binary_IM(
                        sublogs[i],
                        ProcessTree(),
                        activity_key=activity_key,
                        case_key=case_key
                )
                add_child(process_tree, child_node)

            return process_tree
    print(f"Fallback case for log {log}, returning a tau model.")
    return ProcessTree()
# let's test this
if __name__ == "__main__":

    from pm4py.algo.simulation.tree_generator.algorithm import apply as simulate_process_tree
    from pm4py.algo.simulation.playout.process_tree.algorithm import apply as playout_process_tree
    from pm4py.objects.conversion.log.variants.df_to_event_log_1v import apply as df_to_event_log
    from pm4py.algo.discovery.inductive import algorithm as inductive_miner
    from pm4py.objects.conversion.log import converter as log_converter
    from pm4py.visualization.process_tree import visualizer as pt_visualizer
    import pm4py
    def preprocess_log_v2(log):
        idx = 0
        time = 0
        for trace in log:
            for event in trace:
                event['case:concept:name'] = f'case_{idx}'
                event['time_timestamp'] = time
                time += 1
            idx += 1
        return log
    times_BIM = []
    times_pm4py = []
    events = 0
    cases = 0
    for i in range(3):
        process_tree = simulate_process_tree()
        log = preprocess_log_v2(playout_process_tree(process_tree))
        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

        print(f"Log has {len(log)} events and {len(log['concept:name'].unique())} unique activities.")
        # apply the binary IM
        events += len(log)
        cases += len(log['case:concept:name'].unique())
        start_time = pd.Timestamp.now()
        model_bim = apply_binary_IM(log)
        end_time = pd.Timestamp.now()
        times_BIM.append((end_time - start_time).total_seconds())
        start_time = pd.Timestamp.now()
        model_pm4py = inductive_miner.apply(df_to_event_log(log))
        end_time = pd.Timestamp.now()
        times_pm4py.append((end_time - start_time).total_seconds())
        print("==================================")

        print(f"Similarity between Binary IM and PM4Py IM: {pm4py.behavioral_similarity(model_bim, model_pm4py)}")
        print(f"Process tree discovered by Binary IM: {model_bim}")
        print(f"Process tree discovered by PM4Py IM: {model_pm4py}")
        print("==================================")

    # A histogram on runtimes (two boxplots)
    import matplotlib.pyplot as plt
    plt.boxplot([times_BIM, times_pm4py], labels=['Binary IM', 'PM4Py IM'])
    plt.ylabel('Runtime (seconds)')
    plt.title('Runtime Comparison of Binary IM, and PM4Py IM')
    # a subtitle for avg trace len
    avg_trace_len = events / cases if cases > 0 else 0
    plt.suptitle(f'Average Trace Length: {avg_trace_len:.2f}', fontsize=10)
    plt.show()

