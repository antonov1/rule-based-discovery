from fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def apply(log: list[list[str]], **kwargs) -> ProcessTree:
    grandparent = ProcessTree(operator=Operator.LOOP)

    parent = ProcessTree(operator=Operator.XOR)
    add_child(grandparent, parent)

    tau_leaf = ProcessTree()
    add_child(grandparent, tau_leaf)

    activities = sorted({activity for trace in log for activity in trace})
    for activity in activities:
        child = ProcessTree(label=activity)
        add_child(parent=parent, child=child)

    return grandparent
