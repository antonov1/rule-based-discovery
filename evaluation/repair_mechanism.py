import multiprocessing as mp
import os
import random
import signal
import tempfile
import time
import traceback
from contextlib import contextmanager
from typing import Set

import pandas as pd
import pm4py
from inductive_miner.im_utils import normalize_tree, RepairVariant
from inductive_miner.main import (
    apply_IM,
    apply_IM_with_rules,
    preprocess_log as simplify_log,
)
from metrics.fitness import fitness_alignment, fitness_alignment_pm4py
from metrics.precision import (
    precision_alignments_ebi_rust,
    precision_alignments_ebi_rust_sm,
)
from metrics.rule_conformance import conformance
from pm4py.algo.simulation.playout.process_tree.algorithm import (
    apply as playout_process_tree,
)
from pm4py.algo.simulation.tree_generator.algorithm import (
    apply as simulate_process_tree,
)
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.process_tree.obj import ProcessTree
from rule_extraction.from_data import extract

BASE_DIR = "./experiments/repair_mechanism"
LOGS_DIR = f"{BASE_DIR}/logs"
MODELS_DIR = f"{BASE_DIR}/models"
RESULTS_PATH = f"{BASE_DIR}/results.csv"

NUM_TRIALS = 100
MAX_WORKERS = 16
TRIAL_TIMEOUT = 600
INITIAL_SEED = 42


class TimeoutException(Exception):
    pass


# -------------------------------------------------------------------------
# General helpers
# -------------------------------------------------------------------------


def preprocess_log(log):
    """
    Add deterministic case IDs and timestamps to a generated PM4Py log.
    """
    timestamp = 0

    for case_idx, trace in enumerate(log):
        for event in trace:
            event["case:concept:name"] = f"case_{case_idx}"
            event["time:timestamp"] = timestamp
            timestamp += 1

    return log


@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException(f"Timed out after {seconds} seconds")

    old_handler = signal.signal(
        signal.SIGALRM,
        signal_handler,
    )

    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(
            signal.SIGALRM,
            old_handler,
        )


def get_non_tau_leaves(
    node: ProcessTree | None,
) -> Set[str]:
    """
    Return all visible activity labels in a process tree.
    """
    if node is None:
        return set()

    children = getattr(node, "children", None) or []

    if not children:
        if node.label is None:
            return set()

        return {node.label}

    leaves = set()

    for child in children:
        leaves.update(get_non_tau_leaves(child))

    return leaves


def safe_f1(
    fitness: float,
    precision: float,
) -> float:
    denominator = fitness + precision

    if denominator == 0:
        return 0.0

    return 2 * fitness * precision / denominator


def count_petri_net_activities(net) -> int:
    return len(
        {
            transition.label
            for transition in net.transitions
            if transition.label is not None
        }
    )


# -------------------------------------------------------------------------
# Conversion of simplified/pre-pruned traces back into a PM4Py DataFrame
# -------------------------------------------------------------------------


def traces_to_dataframe(
    traces,
) -> pd.DataFrame:
    """
    Convert the simplified trace representation used by the custom
    Inductive Miner/rule implementation back to a PM4Py-compatible
    DataFrame.

    This is required because Split Miner expects an event log/DataFrame,
    whereas rule.repair() operates on the simplified trace representation.
    """
    rows = []

    timestamp = 0

    for case_idx, trace in enumerate(traces):
        case_id = f"prepruned_case_{case_idx}"

        for activity in trace:
            rows.append(
                {
                    "case:concept:name": case_id,
                    "concept:name": activity,
                    "time:timestamp": pd.Timestamp("2026-01-01")
                    + pd.Timedelta(seconds=timestamp),
                }
            )

            timestamp += 1

    return pd.DataFrame(
        rows,
        columns=[
            "case:concept:name",
            "concept:name",
            "time:timestamp",
        ],
    )


# -------------------------------------------------------------------------
# Persistence
# -------------------------------------------------------------------------


def save_result(
    results_path: str,
    row: dict,
) -> None:
    """
    Atomically persist one completed trial.

    The CSV is reloaded from disk before every write, so successful trials
    survive interruptions and the experiment can be resumed.
    """
    results_path = os.path.abspath(results_path)

    os.makedirs(
        os.path.dirname(results_path),
        exist_ok=True,
    )

    trial = str(row["trial"])

    if os.path.exists(results_path) and os.path.getsize(results_path) > 0:
        current = pd.read_csv(results_path)
    else:
        current = pd.DataFrame()

    # Remove an older copy of this trial.
    if not current.empty and "trial" in current.columns:
        current = current[current["trial"].astype(str) != trial].copy()

    current = pd.concat(
        [
            current,
            pd.DataFrame([row]),
        ],
        ignore_index=True,
    )

    current["_trial_sort"] = pd.to_numeric(
        current["trial"],
        errors="coerce",
    )

    current = (
        current.sort_values(
            "_trial_sort",
            na_position="last",
        )
        .drop(columns="_trial_sort")
        .reset_index(drop=True)
    )

    directory = os.path.dirname(results_path)

    fd, tmp_path = tempfile.mkstemp(
        prefix="results_",
        suffix=".tmp",
        dir=directory,
    )

    os.close(fd)

    try:
        current.to_csv(
            tmp_path,
            index=False,
        )

        os.replace(
            tmp_path,
            results_path,
        )

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Verify the result is actually on disk.
    written = pd.read_csv(results_path)

    written_trials = set(written["trial"].astype(str))

    if trial not in written_trials:
        raise RuntimeError(
            f"Trial {trial} could not be found " f"after writing {results_path}"
        )

    print(
        f"Trial {trial}: SAVED " f"({len(written)} completed trials)",
        flush=True,
    )


# -------------------------------------------------------------------------
# Individual model evaluations
# -------------------------------------------------------------------------


def evaluate_process_tree_model(
    log,
    model,
    sampled_rules,
    alphabet,
):
    """
    Calculate the common metrics for a process-tree model.
    """
    num_activities = len(get_non_tau_leaves(model))

    fitness = fitness_alignment(
        log,
        model,
    )

    precision = precision_alignments_ebi_rust(
        log,
        model,
    )

    f1 = safe_f1(
        fitness,
        precision,
    )

    rule_conformance = conformance(
        model,
        sampled_rules,
        alphabet,
    )[0]

    return {
        "acts": num_activities,
        "fitness": fitness,
        "precision": precision,
        "f1": f1,
        "conformance": rule_conformance,
    }


def evaluate_split_miner_model(
    original_log,
    discovery_log,
    sampled_rules,
    alphabet,
):
    """
    Discover Split Miner from the pre-pruned log, but evaluate fitness and
    precision against the original generated event log.
    """
    start = time.perf_counter()

    bpmn = pm4py.discover_bpmn_split_miner(discovery_log)

    net, im, fm = pm4py.convert_to_petri_net(bpmn)

    runtime = time.perf_counter() - start

    fitness = fitness_alignment_pm4py(
        original_log,
        net,
        im,
        fm,
    )

    precision = precision_alignments_ebi_rust_sm(
        original_log,
        (net, im, fm),
    )

    f1 = safe_f1(
        fitness,
        precision,
    )

    rule_conformance = conformance(
        bpmn,
        sampled_rules,
        alphabet,
    )[0]

    return {
        "bpmn": bpmn,
        "net": net,
        "im": im,
        "fm": fm,
        "acts": count_petri_net_activities(net),
        "fitness": fitness,
        "precision": precision,
        "f1": f1,
        "conformance": rule_conformance,
        "time": runtime,
    }


# -------------------------------------------------------------------------
# One complete trial
# -------------------------------------------------------------------------


def evaluate_trial(
    current_idx: int,
    initial_seed: int = INITIAL_SEED,
) -> dict | None:
    """
    One trial consists of:

      1. sample one random process tree
      2. generate its event log
      3. extract declarative rules
      4. sample 1--10 rules
      5. create the common pre-pruned log
      6. discover/evaluate:

           - IM pre-pruning
           - Split Miner pre-pruning
           - RIM Naive
           - RIM TraceLevel
           - RIM EventLevel
           - RIM EditDistance

    Every approach is evaluated on the same original log and same rules.
    """
    random.seed(initial_seed + current_idx)

    try:
        print(
            "",
            flush=True,
        )

        print(
            f"========== TRIAL " f"{current_idx} ==========",
            flush=True,
        )

        # -------------------------------------------------------------
        # Generate process tree and log
        # -------------------------------------------------------------

        process_tree = simulate_process_tree(
            parameters={
                "min": 10,
                "max": 20,
                "mode": 15,
            }
        )

        generated_log = playout_process_tree(process_tree)

        generated_log = preprocess_log(generated_log)

        log_path = os.path.join(
            LOGS_DIR,
            f"log_{current_idx}.xes",
        )

        pm4py.write_xes(
            generated_log,
            log_path,
        )

        log = log_converter.apply(
            generated_log,
            variant=(log_converter.Variants.TO_DATA_FRAME),
        )

        log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

        preprocessed_log = simplify_log(log)

        alphabet = set(log["concept:name"].unique())

        original_acts = len(alphabet)

        # -------------------------------------------------------------
        # Extract and sample rules
        # -------------------------------------------------------------

        rules = extract(
            preprocessed_log,
            min_support=0.5,
            min_confidence=0.5,
        )

        if not rules:
            print(
                f"Trial {current_idx}: " f"no rules extracted",
                flush=True,
            )

            return None

        number_of_rules = random.randint(
            1,
            min(
                len(rules),
                10,
            ),
        )

        sampled_rules = random.sample(
            rules,
            number_of_rules,
        )

        rules_path = os.path.join(
            BASE_DIR,
            f"rules_sampled_" f"{current_idx}.txt",
        )

        with open(
            rules_path,
            "w",
            encoding="utf-8",
        ) as file:
            for rule in sampled_rules:
                file.write(f"{rule}\n")

        # -------------------------------------------------------------
        # Determine percentage of traces satisfying the rules
        # -------------------------------------------------------------

        conforming_log = preprocessed_log.copy()

        for rule in sampled_rules:
            conforming_log = rule.apply(conforming_log)

        conforming_traces_perc = len(conforming_log) / len(preprocessed_log) * 100

        # -------------------------------------------------------------
        # Produce ONE common pre-pruned log.
        #
        # This is shared by:
        #
        #   IM pre-pruning
        #   Split Miner pre-pruning
        # -------------------------------------------------------------

        prepruned_log = preprocessed_log.copy()

        for rule in sampled_rules:
            prepruned_log = rule.repair(prepruned_log)

        if len(prepruned_log) == 0:
            print(
                f"Trial {current_idx}: " f"pre-pruning removed " f"all traces",
                flush=True,
            )

            return None

        prepruned_df = traces_to_dataframe(prepruned_log)

        if prepruned_df.empty:
            print(
                f"Trial {current_idx}: " f"empty pre-pruned " f"DataFrame",
                flush=True,
            )

            return None

        # -------------------------------------------------------------
        # All expensive model discovery/evaluation
        # -------------------------------------------------------------

        with time_limit(TRIAL_TIMEOUT):

            # =========================================================
            # 1. IM + PRE-PRUNING
            # =========================================================

            print(
                f"Trial {current_idx}: " f"IM pre-pruning",
                flush=True,
            )

            start = time.perf_counter()

            model_im_prepruned = normalize_tree(apply_IM(prepruned_log))

            time_im_prepruned = time.perf_counter() - start

            im_prepruned = evaluate_process_tree_model(
                log,
                model_im_prepruned,
                sampled_rules,
                alphabet,
            )

            pm4py.write_ptml(
                model_im_prepruned,
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_im_prepruned.ptml",
                ),
            )

            # =========================================================
            # 2. SPLIT MINER + PRE-PRUNING
            # =========================================================

            print(
                f"Trial {current_idx}: " f"Split Miner pre-pruning",
                flush=True,
            )

            sm_prepruned = evaluate_split_miner_model(
                original_log=log,
                discovery_log=(prepruned_df),
                sampled_rules=(sampled_rules),
                alphabet=alphabet,
            )

            pm4py.write_pnml(
                sm_prepruned["net"],
                sm_prepruned["im"],
                sm_prepruned["fm"],
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_sm_prepruned.pnml",
                ),
            )

            # =========================================================
            # 3. RIM NAIVE
            # =========================================================

            print(
                f"Trial {current_idx}: " f"RIM Naive",
                flush=True,
            )

            start = time.perf_counter()

            model_naive = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=(RepairVariant.Naive),
                )
            )

            time_naive = time.perf_counter() - start

            naive = evaluate_process_tree_model(
                log,
                model_naive,
                sampled_rules,
                alphabet,
            )

            pm4py.write_ptml(
                model_naive,
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_naive.ptml",
                ),
            )

            # =========================================================
            # 4. RIM TRACE LEVEL
            # =========================================================

            print(
                f"Trial {current_idx}: " f"RIM TraceLevel",
                flush=True,
            )

            start = time.perf_counter()

            model_trace = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=(RepairVariant.TraceLevel),
                )
            )

            time_trace = time.perf_counter() - start

            trace = evaluate_process_tree_model(
                log,
                model_trace,
                sampled_rules,
                alphabet,
            )

            pm4py.write_ptml(
                model_trace,
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_trace.ptml",
                ),
            )

            # =========================================================
            # 5. RIM EVENT LEVEL
            # =========================================================

            print(
                f"Trial {current_idx}: " f"RIM EventLevel",
                flush=True,
            )

            start = time.perf_counter()

            model_event = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=(RepairVariant.EventLevel),
                )
            )

            time_event = time.perf_counter() - start

            event = evaluate_process_tree_model(
                log,
                model_event,
                sampled_rules,
                alphabet,
            )

            pm4py.write_ptml(
                model_event,
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_event.ptml",
                ),
            )

            # =========================================================
            # 6. RIM EDIT DISTANCE
            # =========================================================

            print(
                f"Trial {current_idx}: " f"RIM EditDistance",
                flush=True,
            )

            start = time.perf_counter()

            model_edit = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=(RepairVariant.EditDistance),
                )
            )

            time_edit = time.perf_counter() - start

            edit = evaluate_process_tree_model(
                log,
                model_edit,
                sampled_rules,
                alphabet,
            )

            pm4py.write_ptml(
                model_edit,
                os.path.join(
                    MODELS_DIR,
                    f"{current_idx}" f"_edit.ptml",
                ),
            )

        # -------------------------------------------------------------
        # One result row containing the SAME metrics for every method
        # -------------------------------------------------------------

        row = {
            # General characteristics
            "trial": current_idx,
            "num_events": len(log),
            "num_cases": (log["case:concept:name"].nunique()),
            "num_rules": len(sampled_rules),
            "num_acts": original_acts,
            "conforming_traces_perc": (conforming_traces_perc),
            # ---------------------------------------------------------
            # IM + pre-pruning
            # ---------------------------------------------------------
            "IM_Prepruned_acts": (im_prepruned["acts"]),
            "IM_Prepruned_Fitness": (im_prepruned["fitness"]),
            "IM_Prepruned_Precision": (im_prepruned["precision"]),
            "IM_Prepruned_F1": (im_prepruned["f1"]),
            "IM_Prepruned_Conformance": (im_prepruned["conformance"]),
            "Time_IM_Prepruned": (time_im_prepruned),
            # ---------------------------------------------------------
            # Split Miner + pre-pruning
            # ---------------------------------------------------------
            "SM_Prepruned_acts": (sm_prepruned["acts"]),
            "SM_Prepruned_Fitness": (sm_prepruned["fitness"]),
            "SM_Prepruned_Precision": (sm_prepruned["precision"]),
            "SM_Prepruned_F1": (sm_prepruned["f1"]),
            "SM_Prepruned_Conformance": (sm_prepruned["conformance"]),
            "Time_SM_Prepruned": (sm_prepruned["time"]),
            # ---------------------------------------------------------
            # RIM Naive
            # ---------------------------------------------------------
            "RIM_Naive_acts": (naive["acts"]),
            "RIM_Naive_Fitness": (naive["fitness"]),
            "RIM_Naive_Precision": (naive["precision"]),
            "RIM_Naive_F1": (naive["f1"]),
            "RIM_Naive_Conformance": (naive["conformance"]),
            "Time_RIM_Naive": (time_naive),
            # ---------------------------------------------------------
            # RIM TraceLevel
            # ---------------------------------------------------------
            "RIM_TraceLevel_acts": (trace["acts"]),
            "RIM_TraceLevel_Fitness": (trace["fitness"]),
            "RIM_TraceLevel_Precision": (trace["precision"]),
            "RIM_TraceLevel_F1": (trace["f1"]),
            "RIM_TraceLevel_Conformance": (trace["conformance"]),
            "Time_RIM_TraceLevel": (time_trace),
            # ---------------------------------------------------------
            # RIM EventLevel
            # ---------------------------------------------------------
            "RIM_EventLevel_acts": (event["acts"]),
            "RIM_EventLevel_Fitness": (event["fitness"]),
            "RIM_EventLevel_Precision": (event["precision"]),
            "RIM_EventLevel_F1": (event["f1"]),
            "RIM_EventLevel_Conformance": (event["conformance"]),
            "Time_RIM_EventLevel": (time_event),
            # ---------------------------------------------------------
            # RIM EditDistance
            # ---------------------------------------------------------
            "RIM_EditDistance_acts": (edit["acts"]),
            "RIM_EditDistance_Fitness": (edit["fitness"]),
            "RIM_EditDistance_Precision": (edit["precision"]),
            "RIM_EditDistance_F1": (edit["f1"]),
            "RIM_EditDistance_Conformance": (edit["conformance"]),
            "Time_RIM_EditDistance": (time_edit),
        }

        print(
            f"Trial {current_idx}: " f"COMPLETE",
            flush=True,
        )

        return row

    except TimeoutException:
        print(
            f"Trial {current_idx}: " f"TIMED OUT",
            flush=True,
        )

        return None

    except Exception as exc:
        print(
            f"Trial {current_idx} failed: " f"{exc}\n" f"{traceback.format_exc()}",
            flush=True,
        )

        return None


# -------------------------------------------------------------------------
# Main experiment
# -------------------------------------------------------------------------


def evaluate(
    start_idx: int = 0,
    num_trials: int = NUM_TRIALS,
    max_workers: int = MAX_WORKERS,
    results_path: str = RESULTS_PATH,
):
    """
    Sample `num_trials` process trees and evaluate all six approaches.

    The experiment is resumable: trial IDs already present in results.csv
    are skipped.
    """
    os.makedirs(
        LOGS_DIR,
        exist_ok=True,
    )

    os.makedirs(
        MODELS_DIR,
        exist_ok=True,
    )

    results_path = os.path.abspath(results_path)

    # -------------------------------------------------------------
    # Find completed trials
    # -------------------------------------------------------------

    if os.path.exists(results_path) and os.path.getsize(results_path) > 0:
        existing = pd.read_csv(results_path)

        if "trial" in existing.columns:
            completed_ids = set(
                pd.to_numeric(
                    existing["trial"],
                    errors="coerce",
                )
                .dropna()
                .astype(int)
            )
        else:
            completed_ids = set()

    else:
        completed_ids = set()

    requested_trials = list(
        range(
            start_idx,
            start_idx + num_trials,
        )
    )

    remaining_trials = [
        trial for trial in requested_trials if trial not in completed_ids
    ]

    print(
        f"Requested trials: " f"{len(requested_trials)}",
        flush=True,
    )

    print(
        f"Already completed: " f"{len(requested_trials) - len(remaining_trials)}",
        flush=True,
    )

    print(
        f"Remaining: " f"{len(remaining_trials)}",
        flush=True,
    )

    if not remaining_trials:
        return pd.read_csv(results_path)

    # -------------------------------------------------------------
    # Parallel evaluation
    # -------------------------------------------------------------

    context = mp.get_context("forkserver")

    with context.Pool(
        processes=max_workers,
        maxtasksperchild=1,
    ) as pool:

        for row in pool.imap_unordered(
            evaluate_trial,
            remaining_trials,
            chunksize=1,
        ):
            if row is None:
                continue

            # Only the parent process writes to the common CSV.
            save_result(
                results_path,
                row,
            )

    # -------------------------------------------------------------
    # Reload exactly what ended up on disk
    # -------------------------------------------------------------

    if os.path.exists(results_path) and os.path.getsize(results_path) > 0:
        results = pd.read_csv(results_path)

        if "trial" in results.columns:
            results = results.sort_values("trial").reset_index(drop=True)

        return results

    return pd.DataFrame()


if __name__ == "__main__":
    evaluate(
        start_idx=0,
        num_trials=200,
        max_workers=16,
    )
