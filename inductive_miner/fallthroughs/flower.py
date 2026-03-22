from inductive_miner.fallthroughs.fallthrough_utils import add_child
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def apply(im_function, log, **kwargs) -> ProcessTree:
    activities = sorted({activity for trace in log for activity in trace})

    redo_log = [[a] for a in activities]

    parent = ProcessTree(operator=Operator.LOOP)
    do_child = ProcessTree()
    redo_child = im_function(redo_log, ProcessTree())

    add_child(parent, do_child)
    add_child(parent, redo_child)

    return parent
