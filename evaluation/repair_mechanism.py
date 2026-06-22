import os
import random
import signal
from contextlib import contextmanager

import pandas as pd
import pm4py
from inductive_miner.im_utils import normalize_tree, RepairVariant
from inductive_miner.main import (
    apply_IM,
    apply_IM_with_rules,
    preprocess_log as simplify_log,
)
from metrics.fitness import fitness_alignment
from metrics.precision import precision_alignment_tree
from metrics.rule_conformance import conformance
from pm4py.algo.simulation.playout.process_tree.algorithm import (
    apply as playout_process_tree,
)
from pm4py.algo.simulation.tree_generator.algorithm import (
    apply as simulate_process_tree,
)
from pm4py.objects.conversion.log import converter as log_converter
from rule_extraction.from_data import extract


class TimeoutException(Exception):
    pass


@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException(f"Timed out after {seconds} seconds")

    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def preprocess_log(log):
    idx = 0
    time = 0
    for trace in log:
        for event in trace:
            event["case:concept:name"] = f"case_{idx}"
            event["time:timestamp"] = time
            time += 1
        idx += 1
    return log


def evaluate():
    rows = []

    for i in range(0, 1000):
        print(f"Starting trial {i}")

        process_tree = simulate_process_tree()
        log = preprocess_log(playout_process_tree(process_tree))

        os.makedirs("./experiments/repair_mechanism/logs", exist_ok=True)
        pm4py.write_xes(log, f"./experiments/repair_mechanism/logs/log_{i}.xes")

        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)
        preprocessed_log = simplify_log(log)

        log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])
        alphabet = set(log["concept:name"].unique())

        rules = extract(preprocessed_log, min_support=0.8, min_confidence=0.5)

        if len(rules) == 0:
            print(f"No rules extracted, skipping trial {i}")
            continue

        num_sampled = random.randint(1, min(len(rules), 10))
        sampled_rules = random.sample(rules, num_sampled)

        with open(f"./experiments/repair_mechanism/rules_sampled_{i}.txt", "w") as f:
            for r in sampled_rules:
                f.write(str(r) + "\n")

        log_org = preprocessed_log.copy()
        for r in sampled_rules:
            log_org = r.repair(log_org)

        if len(log_org) == 0:
            print(f"All traces were removed by the rules, skipping trial {i}")
            continue

        try:
            with time_limit(420):
                print(f"Trial {i}: discovering prepruned model")
                model_prepruned = normalize_tree(apply_IM(log_org))
                fitness_prepruned = fitness_alignment(log, model_prepruned)
                precision_prepruned = precision_alignment_tree(log, model_prepruned)
                conformance_prepruned = conformance(
                    model_prepruned, sampled_rules, alphabet
                )

                print(f"Trial {i}: trace-level model")
                model_trace = normalize_tree(
                    apply_IM_with_rules(
                        log, rules=sampled_rules, repair_mode=RepairVariant.TraceLevel
                    )
                )
                fitness_trace = fitness_alignment(log, model_trace)
                precision_trace = precision_alignment_tree(log, model_trace)
                conformance_trace = conformance(model_trace, sampled_rules, alphabet)

                print(f"Trial {i}: event-level model")
                model_event = normalize_tree(
                    apply_IM_with_rules(
                        log, rules=sampled_rules, repair_mode=RepairVariant.EventLevel
                    )
                )
                fitness_event = fitness_alignment(log, model_event)
                precision_event = precision_alignment_tree(log, model_event)
                conformance_event = conformance(model_event, sampled_rules, alphabet)

                print(f"Trial {i}: edit-distance model")
                model_edit = normalize_tree(
                    apply_IM_with_rules(
                        log, rules=sampled_rules, repair_mode=RepairVariant.EditDistance
                    )
                )
                fitness_edit = fitness_alignment(log, model_edit)
                precision_edit = precision_alignment_tree(log, model_edit)
                conformance_edit = conformance(model_edit, sampled_rules, alphabet)

        except TimeoutException:
            print(f"Trial {i} timed out, skipping")
            continue
        except Exception as e:
            print(f"Trial {i} failed: {e}")
            continue

        rows.append(
            {
                "trial": i,
                "num_events": len(log),
                "num_cases": log["case:concept:name"].nunique(),
                "num_rules": len(sampled_rules),
                "Prepruned_Fitness": fitness_prepruned,
                "Prepruned_Precision": precision_prepruned,
                "Prepruned_Conformance": conformance_prepruned[0],
                "RIM_Fitness_TraceLevel": fitness_trace,
                "RIM_Precision_TraceLevel": precision_trace,
                "RIM_Conformance_TraceLevel": conformance_trace[0],
                "RIM_Fitness_EventLevel": fitness_event,
                "RIM_Precision_EventLevel": precision_event,
                "RIM_Conformance_EventLevel": conformance_event[0],
                "RIM_Fitness_EditDistance": fitness_edit,
                "RIM_Precision_EditDistance": precision_edit,
                "RIM_Conformance_EditDistance": conformance_edit[0],
            }
        )

        pd.DataFrame(rows).to_csv(
            "./experiments/repair_mechanism/results.csv",
            index=False,
        )

    results = pd.DataFrame(rows)
    results.to_csv("./experiments/repair_mechanism/results.csv", index=False)


if __name__ == "__main__":
    evaluate()
