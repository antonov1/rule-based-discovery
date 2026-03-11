from cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from cuts.loop_cut import BinaryLoopCut, LoopCut
from cuts.sequence import BinarySequenceCut, SequenceCut
import pandas as pd
from utils.directly_follows_graph import DirectlyFollowsGraph
from pm4py.objects.process_tree.obj import ProcessTree, Operator

def base_cases(log : pd.DataFrame, process_tree: ProcessTree, dfg_graph, activity_key = 'concept:name', case_key = 'case:concept:name'):
    if len(dfg_graph.nodes) == 0:
        # This means we have only empty traces, so we return a process tree with a single tau node
        return process_tree
    elif len(dfg_graph.nodes) == 1:
        # This is rather specific case, we have to check if the single activity has no loop
        node = list(dfg_graph.nodes)[0]
        if dfg_graph.has_edge(node, node):
            # Check if None is part of the log
            if None in log:
                # We have a loop, activity is on the right side
                process_tree = ProcessTree(operator=Operator.LOOP)
                process_tree.children.append(ProcessTree())
                process_tree.children.append(ProcessTree(label=node))
                return process_tree
            else:
                # We have a loop, activity is on the left side
                process_tree = ProcessTree(operator=Operator.LOOP)
                process_tree.children.append(ProcessTree(label=node))
                process_tree.children.append(ProcessTree())
                return process_tree
        else:
            # We have no loop, so we return a process tree with a single activity node
            return ProcessTree(label=node)
        

def apply_IM(log : pd.DataFrame, process_tree : ProcessTree, activity_key = 'concept:name', case_key = 'case:concept:name'):
    dfg = DirectlyFollowsGraph(log, activity_key=activity_key, case_key=case_key)
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
                process_tree.children.append(child_node)

            return process_tree
    return ProcessTree()

def apply_binary_IM(log : pd.DataFrame, process_tree : ProcessTree, activity_key = 'concept:name', case_key = 'case:concept:name'):
    dfg = DirectlyFollowsGraph(log, activity_key=activity_key, case_key=case_key)
    dfg_graph = dfg.graph
    # Try to apply the cuts in order of precedence
    cut_classes = [BinaryExclusiveChoiceCut, BinarySequenceCut, BinaryConcurrentCut, BinaryLoopCut]
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
                child_node = apply_binary_IM(
                        sublogs[i],
                        ProcessTree(),
                        activity_key=activity_key,
                        case_key=case_key
                )
                process_tree.children.append(child_node)

            return process_tree
    return ProcessTree()
# let's test this
if __name__ == "__main__":

    """
    log = pd.DataFrame({
        'case:concept:name': ['A', 'A', 'B', 'B', 'C', 'C'],
        'concept:name': ['a', 'b', 'a', 'b', 'a', 'b']
    })
    process_tree = ProcessTree()
    result_tree = apply_binary_IM(log, process_tree)
    print(result_tree)
    from pm4py.visualization.process_tree import visualizer as pt_visualizer
    gviz = pt_visualizer.apply(result_tree)
    pt_visualizer.view(gviz)
    # example 2 c -> a -> c and c -> b -> c
    log2 = pd.DataFrame({
        'case:concept:name': ['A', 'A', 'A', 'B', 'B', 'B'],
        'concept:name': ['c', 'a', 'c', 'c', 'b', 'c']
    })
    process_tree2 = ProcessTree()
    result_tree2 = apply_binary_IM(log2, process_tree2)
    print(result_tree2)
    log3 = pd.DataFrame({
        'case:concept:name' : ['A', 'B', 'B', 'C', 'C', 'C', 'C'],
        'concept:name' : ['c', 'a', 'c', 'a', 'b', 'a', 'c'],
        'time:timestamp' : [1, 2, 3, 4, 5, 6, 7]
    })
    process_tree3 = ProcessTree()
    result_tree3 = apply_binary_IM(log3, process_tree3)
    print(result_tree3)
    # IM from pm4py

    log_optional_prefix = pd.DataFrame({
        'case:concept:name': ['A','B','B','C','C'],
        'concept:name':      ['b','a','b','a','b'],
        'time:timestamp':    [1,2,3,4,5]
    })
    process_tree_optional_prefix = ProcessTree()
    result_tree_optional_prefix = apply_binary_IM(log_optional_prefix, process_tree_optional_prefix)
    print(result_tree_optional_prefix)
    log_xor = pd.DataFrame({
    'case:concept:name': ['A','B','C','D'],
    'concept:name':      ['a','b','a','b'],
    'time:timestamp':    [1,2,3,4]
    })
    process_tree_xor = ProcessTree()
    result_tree_xor = apply_binary_IM(log_xor, process_tree_xor)
    print(result_tree_xor)
    log_long_seq = pd.DataFrame({
    'case:concept:name': ['A','A','A','B','B','B','C','C','C'],
    'concept:name':      ['a','b','c','a','b','c','a','b','c'],
    'time:timestamp':    [1,2,3,4,5,6,7,8,9]
    })
    process_tree_long_seq = ProcessTree()
    result_tree_long_seq = apply_binary_IM(log_long_seq, process_tree_long_seq)
    print(result_tree_long_seq)
    """
    from pm4py.algo.simulation.playout.process_tree.algorithm import Variants
    from pm4py.algo.simulation.tree_generator.algorithm import apply as simulate_process_tree
    from pm4py.algo.simulation.playout.process_tree.algorithm import apply as playout_process_tree
    from pm4py.objects.conversion.log.variants.df_to_event_log_1v import apply as df_to_event_log
    from pm4py.algo.discovery.inductive import algorithm as inductive_miner
    from pm4py.objects.conversion.log import converter as log_converter


    import datetime
    def preprocess_log(log):
        idx = 0
        time = 0
        for trace in log:
            for event in trace:
                event['case:concept:name'] = f'case_{idx}'
                event['time_timestamp'] = time
                time += 1
            idx += 1
        return log
        return new_log
    times_BIM = []
    times_SIM = []
    times_pm4py = []
    events = 0
    cases = 0
    for i in range(20):
        process_tree = simulate_process_tree()
        log = preprocess_log(playout_process_tree(process_tree))
        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

        print(f"Log has {len(log)} events and {len(log['concept:name'].unique())} unique activities.")
        # apply the binary IM
        events += len(log)
        cases += len(log['case:concept:name'].unique())
        start_time = datetime.datetime.now()
        result_tree = apply_binary_IM(log, ProcessTree())
        end_time = datetime.datetime.now()
        times_BIM.append((end_time - start_time).total_seconds())
        start_time = datetime.datetime.now()
        result_tree_SIM = apply_IM(log, ProcessTree())
        end_time = datetime.datetime.now()
        times_SIM.append((end_time - start_time).total_seconds())
        # apply the pm4py IM
        start_time = datetime.datetime.now()
        result_tree_pm4py = inductive_miner.apply(df_to_event_log(log))
        end_time = datetime.datetime.now()
        times_pm4py.append((end_time - start_time).total_seconds())
    # A histogram on runtimes (two boxplots)
    import matplotlib.pyplot as plt
    plt.boxplot([times_BIM, times_SIM, times_pm4py], labels=['Binary IM', 'IM', 'PM4Py IM'])
    plt.ylabel('Runtime (seconds)')
    plt.title('Runtime Comparison of Binary IM, IM, and PM4Py IM')
    # a subtitle for avg trace len
    avg_trace_len = events / cases if cases > 0 else 0
    plt.suptitle(f'Average Trace Length: {avg_trace_len:.2f}', fontsize=10)
    plt.show()

