from cuts.concurrent_cut import BinaryConcurrentCut
from cuts.exclusive import BinaryExclusiveChoiceCut
from cuts.loop_cut import BinaryLoopCut
from cuts.sequence import BinarySequenceCut
import pandas as pd
from utils.directly_follows_graph import DirectlyFollowsGraph
from pm4py.objects.process_tree.obj import ProcessTree, Operator

def base_cases(log : pd.DataFrame, process_tree: ProcessTree, activity_key = 'concept:name', case_key = 'case:concept:name'):
    dfg = DirectlyFollowsGraph(log, activity_key=activity_key, case_key=case_key)
    dfg_graph = dfg.graph
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
                process_tree.children.append(ProcessTree(), ProcessTree(label=node))
                return process_tree
            else:
                # We have a loop, activity is on the left side
                process_tree = ProcessTree(operator=Operator.LOOP)
                process_tree.children.append(ProcessTree(label=node), ProcessTree())
                return process_tree
        else:
            # We have no loop, so we return a process tree with a single activity node
            return ProcessTree(label=node)
def apply_binary_IM(log : pd.DataFrame, process_tree : ProcessTree, activity_key = 'concept:name', case_key = 'case:concept:name'):
    dfg = DirectlyFollowsGraph(log, activity_key=activity_key, case_key=case_key)
    dfg_graph = dfg.graph
    # Try to apply the cuts in order of precedence
    cut_classes = [BinaryExclusiveChoiceCut, BinarySequenceCut, BinaryConcurrentCut, BinaryLoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    if len(dfg_graph.nodes) <= 1:
        print(f"Applying base case with log having {len(dfg_graph.nodes)} activities.")
        return base_cases(log, process_tree, activity_key=activity_key, case_key=case_key)
        
        
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if groups is not None:
            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(log, groups, activity_key=activity_key, case_key=case_key)

            print(f"Applying {cut.name} with groups: {groups}")
            for i in range(len(sublogs)):
                child_node = apply_binary_IM(
                        sublogs[i],
                        ProcessTree(),
                        activity_key=activity_key,
                        case_key=case_key
                )
                process_tree.children.append(child_node)
            print(f"The process tree looks like this: {process_tree}")

            return process_tree
    print("No applicable cuts found.")
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
    """
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