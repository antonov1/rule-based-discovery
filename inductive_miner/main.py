from typing import List, Union

import pandas as pd
import pm4py
from inductive_miner.cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from inductive_miner.cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from inductive_miner.cuts.loop_cut import BinaryLoopCut, LoopCut
from inductive_miner.cuts.strict_sequence import (
    BinaryStrictSequenceCut,
    StrictSequenceCut,
)
from inductive_miner.fallthroughs import (
    activity_concur,
    activity_once,
    empty,
    flower_model,
    n_tau,
    s_tau,
)
from inductive_miner.im_utils import add_child, base_cases, repair_behavior
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from rules import (
    AbstractRule,
    AtMostOnceRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)
from utils.directly_follows_graph import DirectlyFollowsGraph

ENABLE_PRINTS = True


def handle_empty_traces(log, im_function, rules: List[AbstractRule] = None):
    if any(len(trace) == 0 for trace in log):
        # Remove empty traces from the log
        non_empty_log = [t for t in log if len(t) > 0]

        if rules:
            act_set = set([act for trace in log for act in trace])
            groups = [set(), act_set]
            unsat_rules = ExclusiveChoiceCut.check_rules(rules, groups)
            if len(unsat_rules) > 0:
                return repair_behavior(log, unsat_rules, im_function, rules)

        if not non_empty_log:
            return ProcessTree()  # Pure Tau

        # Recursively mine the non-empty part and wrap in XOR

        subtree = (
            im_function(non_empty_log, rules)
            if rules is not None
            else im_function(non_empty_log)
        )
        root = ProcessTree(operator=Operator.XOR)
        add_child(root, ProcessTree())  # Add Tau
        add_child(root, subtree)  # Add the actual process
        return root
    return None


def preprocess_log(log, activity_key="concept:name", case_key="case:concept:name"):
    return log.groupby(case_key)[activity_key].apply(list).tolist()


def apply_IM_with_rules(
    log: Union[pd.DataFrame, List],
    rules: List[AbstractRule] = [],
    activity_key="concept:name",
    case_key="case:concept:name",
):
    # print(f"Rules are: {rules}")
    # print(f"Log is: {log}")
    # First, we can apply the rules to filter the log
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    empty_traces = handle_empty_traces(log, apply_IM_with_rules, rules=rules)
    print(f"Log is: {log}")
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, apply_IM_with_rules, rules
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

        return process_tree
    log_act_set = set([act for trace in log for act in trace])
    for cut_class, op in zip(cut_classes, ops):
        cut = cut_class(dfg_graph)
        groups = cut.discover()
        if ENABLE_PRINTS:
            print(f"Cut {op} discovered with groups {groups}")
        if groups is not None:
            if ENABLE_PRINTS:
                print(f"Groups are: {groups}")
            unsat_rules = cut.check_rules(rules, groups)
            if ENABLE_PRINTS:
                print(
                    f"Unsat rules for {op} with groups {groups}: {[str(r) for r in unsat_rules]}"
                )
            if unsat_rules:
                repaired_log = repair_behavior(
                    log, unsat_rules, apply_IM_with_rules, rules
                )
                if repaired_log:
                    return repaired_log
                else:
                    continue

            process_tree = ProcessTree(operator=op)
            sublogs = cut.project(
                log, groups, activity_key=activity_key, case_key=case_key
            )
            projected_rules = cut.project_rules(rules, groups)
            for i in range(len(sublogs)):
                child_node = apply_IM_with_rules(
                    sublogs[i],
                    projected_rules[i],
                    activity_key=activity_key,
                    case_key=case_key,
                )
                add_child(process_tree, child_node)
            if ENABLE_PRINTS:
                print("***")
                print("ACTS:", sorted(log_act_set))
                print("RULES:", [str(r) for r in rules])
                print("OP:", op)
                print("GROUPS:", [sorted(g) for g in groups])
                print(
                    "PROJECTED RULES:", [proj_group for proj_group in projected_rules]
                )
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
            im_function=apply_IM_with_rules,
            rules=rules,
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


def apply_IM(
    log: Union[pd.DataFrame, List],
    activity_key="concept:name",
    case_key="case:concept:name",
):

    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)

    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    log_act_set = set([act for trace in log for act in trace])
    # Try to apply the cuts in order of precedence
    cut_classes = [ExclusiveChoiceCut, StrictSequenceCut, ConcurrentCut, LoopCut]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]
    # Check if the log has exactly one activity or empty traces
    empty_traces = handle_empty_traces(log, apply_IM)
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        # print(f"Applying base case to log {log}")
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )
        if ENABLE_PRINTS:
            print(f"BASE CASE TREE {process_tree}")

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
                    sublog, activity_key=activity_key, case_key=case_key
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
    activity_key="concept:name",
    case_key="case:concept:name",
):
    if isinstance(log, pd.DataFrame):
        # transform it to a list of traces
        log = preprocess_log(log, activity_key=activity_key, case_key=case_key)
    process_tree = ProcessTree()

    dfg = DirectlyFollowsGraph(log)
    dfg_graph = dfg.graph

    empty_traces = handle_empty_traces(log, apply_IM)
    if empty_traces is not None:
        return empty_traces

    if len(dfg_graph.nodes) <= 1:
        parent = process_tree.parent
        process_tree = base_cases(
            log, process_tree, dfg_graph, activity_key=activity_key, case_key=case_key
        )

        process_tree.parent = parent
        return process_tree

    # Try to apply the cuts in order of precedence

    cut_classes = [
        BinaryExclusiveChoiceCut,
        BinaryStrictSequenceCut,
        BinaryConcurrentCut,
        BinaryLoopCut,
    ]
    ops = [Operator.XOR, Operator.SEQUENCE, Operator.PARALLEL, Operator.LOOP]

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
    for _, fallthrough in enumerate(order_of_fall_throughs):
        res = fallthrough(
            dfg=dfg.graph,
            start_activities=start_activities,
            end_activities=end_activities,
            log=log,
            cut_order=cut_classes,
            im_function=apply_binary_IM,
            binary=True,
        )
        if res:
            res.parent = process_tree.parent
            return res
    return ProcessTree()


if __name__ == "__main__":
    examples = [
        {
            "name": "1. Enforce existence even though part of the log misses A",
            "log": [["B"], ["A", "B"], ["B", "C"]],
            "rules": [ExistenceRule("A")],
            "why": "Some traces do not contain A, but the discovered model should require A.",
        },
        {
            "name": "2. Enforce at-most-once although the log repeats A",
            "log": [["A", "B", "A"], ["A"], ["B", "A", "C"]],
            "rules": [AtMostOnceRule("A")],
            "why": "The log contains repetitions of A, but the resulting model should not allow A more than once.",
        },
        {
            "name": "3. Enforce not-coexistence even though A and B co-occur in the log",
            "log": [["A"], ["B"], ["A", "B"], ["A"]],
            "rules": [NotCoExistenceRule(["A", "B"])],
            "why": "The trace ['A', 'B'] violates the rule, but the model should separate A and B so they cannot co-exist.",
        },
        {
            "name": "4. Enforce co-existence although the log has A without B",
            "log": [["A"], ["A", "B"], ["B"], ["A", "B"]],
            "rules": [CoExistenceRule(["A", "B"])],
            "why": "The log is inconsistent, but the model should enforce that A and B always appear together.",
        },
        {
            "name": "5. Enforce initialization although one trace starts with B",
            "log": [["B", "A"], ["A", "C"], ["A", "B"]],
            "rules": [InitializationRule("A")],
            "why": "The first trace violates the rule, but the model should start with A.",
        },
        {
            "name": "6. Enforce end rule although one trace ends with C",
            "log": [["A", "B"], ["C", "B"], ["A", "C"]],
            "rules": [EndRule("B")],
            "why": "Not all traces end in B, but the resulting model should.",
        },
        {
            "name": "7. Enforce precedence A -> B although B appears without A",
            "log": [["B"], ["A", "B"], ["C", "A", "B"]],
            "rules": [PrecedenceRule(["A", "B"])],
            "why": "The first trace violates precedence, but the model should require A before B.",
        },
        {
            "name": "8. Enforce response A -> B although some A is not followed by B",
            "log": [["A"], ["A", "C"], ["A", "B"], ["C"]],
            "rules": [ResponseRule(["A", "B"])],
            "why": "Some occurrences of A are not followed by B, but the model should enforce that they are.",
        },
        {
            "name": "9. Enforce responded existence A -> B although A occurs alone",
            "log": [["A"], ["A", "B"], ["C"], ["B"]],
            "rules": [RespondedExistenceRule(["A", "B"])],
            "why": "A appears without B in one trace, but the model should ensure that if A occurs, B occurs too.",
        },
        {
            "name": "10. Enforce not-succession A !-> B although the log contains A then B",
            "log": [["A", "B"], ["A", "C"], ["B"]],
            "rules": [NotSuccessionRule(["A", "B"])],
            "why": "The first trace violates the rule, but the model should disallow B after A.",
        },
        {
            "name": "11. Combine initialization and end with noisy traces",
            "log": [["B", "A"], ["A", "C"], ["A", "B"], ["A", "D", "C"]],
            "rules": [InitializationRule("A"), EndRule("C")],
            "why": "The first trace does not start with A and one trace ends with B, but the model should start with A and end with C.",
        },
        {
            "name": "12. Combine existence and at-most-once",
            "log": [["A", "B", "A"], ["B"], ["A", "C"]],
            "rules": [ExistenceRule("A"), AtMostOnceRule("A")],
            "why": "The model should require A, but also forbid repeating it.",
        },
        {
            "name": "13. Combine precedence and response",
            "log": [["B"], ["A"], ["A", "B"], ["C", "A", "D"]],
            "rules": [PrecedenceRule(["A", "B"]), ResponseRule(["A", "B"])],
            "why": "B should only happen after A, and every A should be followed by B, despite contradictory traces.",
        },
        {
            "name": "14. Combine not-coexistence with existence",
            "log": [["A"], ["B"], ["A", "B"], ["C"]],
            "rules": [ExistenceRule("A"), NotCoExistenceRule(["A", "B"])],
            "why": "The model should require A but still forbid A and B from appearing together.",
        },
        {
            "name": "15. Combine co-existence with initialization",
            "log": [["A"], ["B"], ["A", "B"], ["C", "A", "B"]],
            "rules": [InitializationRule("A"), CoExistenceRule(["A", "B"])],
            "why": "The model should start with A and enforce that A and B always occur together.",
        },
        {
            "name": "16. Initialization + co-existence + end, with noisy optional behavior",
            "log": [
                ["A", "B", "D", "E"],
                ["A", "B", "E"],
                ["B", "E"],  # violates initialization
                ["A", "D", "E"],  # violates co-existence
                ["A", "B", "D"],  # violates end
                ["C", "A", "B", "E"],  # violates initialization
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule(["A", "B"]),
                EndRule("E"),
            ],
            "why": (
                "A should always be the first activity, A and B should always appear together, "
                "and every valid execution should end in E. The log contains several traces "
                "that violate one or more of these constraints."
            ),
        },
        {
            "name": "17. Initialization + co-existence + at-most-once + not-succession",
            "log": [
                ["A", "B", "C"],
                ["A", "B", "D"],
                ["A", "B", "C", "B"],  # violates at-most-once(B)
                ["B", "A", "C"],  # violates initialization
                ["A", "C"],  # violates co-existence
                ["A", "B", "C", "D"],  # violates not-succession(C, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule(["A", "B"]),
                AtMostOnceRule("B"),
                NotSuccessionRule(["C", "D"]),
            ],
            "why": (
                "This one is more interesting because the rules interact: A must start, "
                "A and B must always occur together, B cannot repeat, and D must not come "
                "after C. The log contains traces that break each of these in different ways."
            ),
        },
        {
            "name": "18. Initialization + co-existence + response + not-coexistence",
            "log": [
                ["A", "B", "D"],
                ["A", "B", "C", "D"],  # violates not-coexistence(C, D)
                ["B", "D"],  # violates initialization
                ["A", "D"],  # violates co-existence
                ["A", "B"],  # violates response(B, D)
                ["A", "B", "C"],  # violates response(B, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule(["A", "B"]),
                ResponseRule(["B", "D"]),
                NotCoExistenceRule(["C", "D"]),
            ],
            "why": (
                "A must be first, A and B must occur together, every B must eventually be "
                "followed by D, and C and D must never appear together. This forces the "
                "model to balance positive and negative constraints at once."
            ),
        },
        {
            "name": "19. Initialization + co-existence + precedence + end",
            "log": [
                ["A", "B", "C", "E"],
                ["A", "B", "E"],
                ["B", "A", "E"],  # violates initialization
                ["A", "C", "E"],  # violates co-existence
                ["A", "B", "E", "C"],  # violates end
                ["A", "B", "D", "C", "E"],
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule(["A", "B"]),
                PrecedenceRule(["B", "C"]),
                EndRule("E"),
            ],
            "why": (
                "A must start, A and B must always occur together, C may only happen if B "
                "already happened, and E must be the end activity."
            ),
        },
        {
            "name": "20. Initialization + co-existence + responded existence + at-most-once",
            "log": [
                ["A", "B", "D"],
                ["A", "B"],
                ["A", "D"],  # violates co-existence
                ["B", "D"],  # violates initialization
                ["A", "B", "B", "D"],  # violates at-most-once(B)
                ["A", "B", "C"],  # violates responded existence(B, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule(["A", "B"]),
                RespondedExistenceRule(["B", "D"]),
                AtMostOnceRule("B"),
            ],
            "why": (
                "Whenever B appears, D must also appear somewhere in the same trace; A and B "
                "must always occur together; A must be first; and B cannot repeat."
            ),
        },
    ]
    for ex in examples:
        print(f"\n--- {ex['name']} ---")
        print("Log:", ex["log"])
        print("Rules:", ex["rules"])
        print("Why:", ex["why"])
        model_constrainted = apply_IM_with_rules(ex["log"], ex["rules"])
        model_im = apply_IM(ex["log"])
        print(f"IM (no constraints): {model_im}")
        print(f"RIM: {model_constrainted}")
        print(
            f"Semantic similarity with IM (no constraints): {pm4py.behavioral_similarity(model_constrainted, model_im)}"
        )
