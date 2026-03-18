import pandas as pd
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def add_child(parent, child):
    child.parent = parent
    parent.children.append(child)


def base_cases(
    log: pd.DataFrame,
    process_tree: ProcessTree,
    dfg_graph,
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if len(dfg_graph.nodes) == 0:
        # This means we have only empty traces, so we return a process tree with a single tau node
        return process_tree
    elif len(dfg_graph.nodes) == 1 or (
        len(dfg_graph.nodes) == 2 and "ArtificialNoneNode" in dfg_graph.nodes
    ):
        # This is rather specific case, we have to check if the single activity has no loop
        activity_node = [n for n in dfg_graph.nodes if n != "ArtificialNoneNode"]
        if not activity_node:
            new_tree = ProcessTree()
            return new_tree
        activity_node = activity_node[0]
        if dfg_graph.has_edge(activity_node, activity_node):
            # Check if None is part of the log
            if [] in log:
                # We have a loop, activity is on the right side
                process_tree = ProcessTree(operator=Operator.LOOP)
                tau_leaf = ProcessTree()
                tau_leaf.parent = process_tree
                activity_leaf = ProcessTree(label=activity_node)
                activity_leaf.parent = process_tree
                process_tree.children.extend([tau_leaf, activity_leaf])
                return process_tree
            else:
                # We have a loop, activity is on the left side
                process_tree = ProcessTree(operator=Operator.LOOP)
                activity_tree = ProcessTree(label=activity_node)
                activity_tree.parent = process_tree
                tau_leaf = ProcessTree()
                tau_leaf.parent = process_tree
                process_tree.children.extend([activity_tree, tau_leaf])

                return process_tree
        else:
            # We have no loop, so we return a process tree with a single activity node
            process_tree = ProcessTree(label=activity_node)
            return process_tree

    print(
        f"For log {log} we have more than one activity, but we couldn't find any cut. This should not happen."
    )
    raise Exception("Base case error: more than one activity but no cut found")
