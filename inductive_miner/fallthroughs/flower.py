from inductive_miner.cuts import LoopCut
from inductive_miner.fallthroughs.fallthrough_utils import add_child
from inductive_miner.im_utils import repair_mechanism
from pm4py.objects.process_tree.obj import Operator, ProcessTree


def apply(im_function, log, rules=None, rule_strictness=1, **kwargs) -> ProcessTree:
    activities = sorted({activity for trace in log for activity in trace})
    if len(activities) < 2:
        return None
    redo_log = [[a] for a in activities]
    groups = [set(), set(activities)]

    if rules:
        unsat_rules = LoopCut.check_rules(rules, groups)
        rule_conf = 1 - len(unsat_rules) / len(rules) if rules else 1
        if rule_conf < rule_strictness:
            print(f"Unsatisfied rules: {unsat_rules}, rule confidence: {rule_conf}")
            return repair_mechanism(
                log, unsat_rules, im_function, rules, rule_strictness=rule_strictness
            )

    parent = ProcessTree(operator=Operator.LOOP)
    do_child = ProcessTree()
    proj_rules = LoopCut.project_rules(rules, groups)[1] if rules else None
    redo_child = (
        im_function(redo_log, proj_rules, rule_strictness=rule_strictness)
        if proj_rules
        else im_function(redo_log)
    )

    add_child(parent, do_child)
    add_child(parent, redo_child)

    return parent
