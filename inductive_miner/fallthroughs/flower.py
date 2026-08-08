from inductive_miner.cuts import LoopCut
from inductive_miner.im_utils import Decomposition
from pm4py.objects.process_tree.obj import Operator


def apply(
    log,
    rules=None,
    **kwargs,
) -> Decomposition:
    activities = sorted({activity for trace in log for activity in trace})
    if len(activities) < 2:
        return None
    redo_log = [[a] for a in activities]
    groups = [set(), set(activities)]

    return Decomposition(
        operator=Operator.LOOP,
        sublogs=[[], redo_log],
        projected_rules=LoopCut.project_rules(rules, groups) if rules else None,
    )
