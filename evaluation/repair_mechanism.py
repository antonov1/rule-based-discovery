import multiprocessing as mp
import os
import random
import re
import signal
import tempfile
import time
import traceback
from contextlib import contextmanager
from typing import List, Set

import pandas as pd
import pm4py
from inductive_miner.im_utils import normalize_tree, RepairVariant
from inductive_miner.main import (
    apply_IM,
    apply_IM_with_rules,
    apply_IM_with_rules,
    preprocess_log as simplify_log,
)
from llm_connection.query import code_extraction
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


class TimeoutException(Exception):
    pass


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


def get_non_tau_leaves(node: ProcessTree | None) -> Set[str]:
    """Return the labels of all non-tau leaves in a process tree."""
    if node is None:
        return set()

    children = getattr(node, "children", None) or []

    if not children:
        return {node.label} if node.label is not None else set()

    leaves: Set[str] = set()

    for child in children:
        leaves.update(get_non_tau_leaves(child))

    return leaves


def evaluate_trial(current_idx: int, initial_seed: int = 42) -> dict | None:
    # Reproducibility reasons
    random.seed(initial_seed + current_idx)

    try:
        print(f"[PID {os.getpid()}] Starting trial {current_idx}", flush=True)

        process_tree = simulate_process_tree()
        log = preprocess_log(playout_process_tree(process_tree))

        pm4py.write_xes(
            log,
            f"./experiments/repair_mechanism/logs/log_{current_idx}.xes",
        )

        log = log_converter.apply(
            log,
            variant=log_converter.Variants.TO_DATA_FRAME,
        )
        preprocessed_log = simplify_log(log)

        log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])
        alphabet = set(log["concept:name"].unique())

        rules = extract(
            preprocessed_log,
            min_support=0.5,
            min_confidence=0.5,
        )

        if not rules:
            print(f"Trial {current_idx}: no rules extracted", flush=True)
            return None

        sampled_rules = random.sample(
            rules,
            random.randint(1, min(len(rules), 10)),
        )

        with open(
            f"./experiments/repair_mechanism/" f"rules_sampled_{current_idx}.txt",
            "w",
        ) as file:
            for rule in sampled_rules:
                file.write(f"{rule}\n")

        log_org = preprocessed_log.copy()

        for rule in sampled_rules:
            log_org = rule.repair(log_org)

        if len(log_org) == 0:
            print(f"Trial {current_idx}: all traces removed", flush=True)
            return None
        len({e for trace in log_org for e in trace})

        with time_limit(600):
            model_prepruned = normalize_tree(apply_IM(log_org))
            len(get_non_tau_leaves(model_prepruned))
            fitness_prepruned = fitness_alignment(log, model_prepruned)
            precision_prepruned = precision_alignments_ebi_rust(
                log,
                model_prepruned,
            )
            conformance_prepruned = conformance(
                model_prepruned,
                sampled_rules,
                alphabet,
            )
            pm4py.write_ptml(
                model_prepruned,
                f"./experiments/repair_mechanism/models/" f"{current_idx}_p.ptml",
            )

            model_trace = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=RepairVariant.TraceLevel,
                )
            )
            fitness_trace = fitness_alignment(log, model_trace)
            precision_trace = precision_alignments_ebi_rust(log, model_trace)
            conformance_trace = conformance(
                model_trace,
                sampled_rules,
                alphabet,
            )
            pm4py.write_ptml(
                model_trace,
                f"./experiments/repair_mechanism/models/" f"{current_idx}_t.ptml",
            )

            model_event = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=RepairVariant.EventLevel,
                )
            )

            fitness_event = fitness_alignment(log, model_event)
            precision_event = precision_alignments_ebi_rust(log, model_event)
            conformance_event = conformance(
                model_event,
                sampled_rules,
                alphabet,
            )
            pm4py.write_ptml(
                model_event,
                f"./experiments/repair_mechanism/models/" f"{current_idx}_e.ptml",
            )

            model_edit = normalize_tree(
                apply_IM_with_rules(
                    log,
                    rules=sampled_rules,
                    repair_mode=RepairVariant.EditDistance,
                )
            )

            fitness_edit = fitness_alignment(log, model_edit)
            precision_edit = precision_alignments_ebi_rust(log, model_edit)
            conformance_edit = conformance(
                model_edit,
                sampled_rules,
                alphabet,
            )
            pm4py.write_ptml(
                model_edit,
                f"./experiments/repair_mechanism/models/" f"{current_idx}_ed.ptml",
            )

        return {
            "trial": current_idx,
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

    except TimeoutException:
        print(f"Trial {current_idx} timed out", flush=True)
        return None
    except Exception as exc:
        print(
            f"Trial {current_idx} failed: {exc}\n" f"{traceback.format_exc()}",
            flush=True,
        )
        return None


def evaluate(
    start_idx: int = 0,
    num_trials: int = 3000,
    max_workers: int = 16,
):
    base_dir = "./experiments/repair_mechanism"
    os.makedirs(f"{base_dir}/logs", exist_ok=True)
    os.makedirs(f"{base_dir}/models", exist_ok=True)

    output_path = f"{base_dir}/results_{start_idx}.csv"
    trial_indices = range(start_idx, start_idx + num_trials)
    rows = []

    context = mp.get_context("forkserver")

    with context.Pool(
        processes=max_workers,
        maxtasksperchild=5,
    ) as pool:
        for row in pool.imap_unordered(
            evaluate_trial,
            trial_indices,
            chunksize=1,
        ):
            if row is None:
                continue

            rows.append(row)
            rows.sort(key=lambda result: result["trial"])

            # Only the parent writes
            pd.DataFrame(rows).to_csv(output_path, index=False)

    results = pd.DataFrame(rows)

    if not results.empty:
        results = results.sort_values("trial").reset_index(drop=True)

    results.to_csv(output_path, index=False)
    return results


def evaluate_dataset(ids: List[str]):
    base_dir = "./experiments/repair_mechanism"
    models_dir = f"{base_dir}/models"
    results_path = f"{base_dir}/results_0.csv"

    os.makedirs(models_dir, exist_ok=True)

    # Load already computed results, if available.
    if os.path.exists(results_path):
        results = pd.read_csv(results_path)

        if "trial" in results.columns:
            # Normalize to strings so IDs such as 1 and "1" compare consistently.
            completed_ids = set(results["trial"].astype(str))
        else:
            completed_ids = set()
    else:
        results = pd.DataFrame()
        completed_ids = set()

    for eval_id in ids:
        # Skip trials that are already present in results.csv.
        if str(eval_id) in completed_ids:
            print(
                f"Trial {eval_id}: already present in results, skipping",
                flush=True,
            )
            continue

        print(f"Starting trial {eval_id}", flush=True)

        try:
            log = pm4py.read_xes(f"{base_dir}/logs/log_{eval_id}.xes")
            log = log_converter.apply(
                log,
                variant=log_converter.Variants.TO_DATA_FRAME,
            )
            preprocessed_log = simplify_log(log)

            log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])
            alphabet = set(log["concept:name"].unique())

            with open(
                f"{base_dir}/rules_sampled_{eval_id}.txt",
                "r",
                encoding="utf-8",
            ) as file:
                code = file.read()

            lines = []

            for line_number, line in enumerate(
                code.splitlines(),
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                lines.append(f"r{line_number} = {line}")

            code = "\n".join(lines)
            code = re.sub(r"\(\s*", "('", code)
            code = re.sub(r"\s*,\s*", "', '", code)
            code = re.sub(r"\s*\)", "')", code)
            code = f"```python\n{code}\n```"

            print(
                f"Code for trial {eval_id}: {code}",
                flush=True,
            )

            _, sampled_rules = code_extraction(
                code,
                activities=list(alphabet),
            )

            if not sampled_rules:
                print(
                    f"Trial {eval_id}: no rules extracted, skipping",
                    flush=True,
                )
                continue

            log_org = preprocessed_log.copy()

            for rule in sampled_rules:
                log_org = rule.repair(log_org)

            if len(log_org) == 0:
                print(
                    f"Trial {eval_id}: all traces were removed, skipping",
                    flush=True,
                )
                continue

            log_copy = preprocessed_log.copy()

            for rule in sampled_rules:
                log_copy = rule.apply(log_copy)

            perc_of_conf_traces = len(log_copy) / len(preprocessed_log) * 100
            original_acts = len({e for trace in preprocessed_log for e in trace})

            # Everything expensive stays under the existing timeout.
            with time_limit(600):
                print(
                    f"Trial {eval_id}: discovering prepruned model",
                    flush=True,
                )

                time_prepruned = time.perf_counter()
                model_prepruned = normalize_tree(apply_IM(log_org))
                time_prepruned = time.perf_counter() - time_prepruned

                fitness_prepruned = fitness_alignment(
                    log,
                    model_prepruned,
                )
                precision_prepruned = precision_alignments_ebi_rust(
                    log,
                    model_prepruned,
                )
                f1_prepruned = (
                    2
                    * fitness_prepruned
                    * precision_prepruned
                    / (fitness_prepruned + precision_prepruned)
                )

                prepruned_acts = len(get_non_tau_leaves(model_prepruned))

                conformance_prepruned = conformance(
                    model_prepruned,
                    sampled_rules,
                    alphabet,
                )

                pm4py.write_ptml(
                    model_prepruned,
                    f"{models_dir}/{eval_id}_p.ptml",
                )

                print(
                    f"Trial {eval_id}: no-repair model",
                    flush=True,
                )

                time_norepair = time.perf_counter()

                model_norepair = normalize_tree(
                    apply_IM_with_rules(
                        log,
                        rules=sampled_rules,
                        repair_mode=RepairVariant.Naive,
                    )
                )

                time_norepair = time.perf_counter() - time_norepair

                norepair_acts = len(get_non_tau_leaves(model_norepair))

                fitness_norepair = fitness_alignment(
                    log,
                    model_norepair,
                )
                precision_norepair = precision_alignments_ebi_rust(
                    log,
                    model_norepair,
                )
                f1_norepair = (
                    2
                    * fitness_norepair
                    * precision_norepair
                    / (fitness_norepair + precision_norepair)
                )
                conformance_norepair = conformance(
                    model_norepair,
                    sampled_rules,
                    alphabet,
                )

                print(
                    f"Trial {eval_id}: trace-level model",
                    flush=True,
                )

                time_trace = time.perf_counter()

                model_trace = normalize_tree(
                    apply_IM_with_rules(
                        log,
                        rules=sampled_rules,
                        repair_mode=RepairVariant.TraceLevel,
                    )
                )

                time_trace = time.perf_counter() - time_trace

                trace_acts = len(get_non_tau_leaves(model_trace))

                fitness_trace = fitness_alignment(
                    log,
                    model_trace,
                )
                precision_trace = precision_alignments_ebi_rust(
                    log,
                    model_trace,
                )
                f1_trace = (
                    2
                    * fitness_trace
                    * precision_trace
                    / (fitness_trace + precision_trace)
                )
                conformance_trace = conformance(
                    model_trace,
                    sampled_rules,
                    alphabet,
                )

                pm4py.write_ptml(
                    model_trace,
                    f"{models_dir}/{eval_id}_t.ptml",
                )

                print(
                    f"Trial {eval_id}: event-level model",
                    flush=True,
                )

                time_event = time.perf_counter()

                model_event = normalize_tree(
                    apply_IM_with_rules(
                        log,
                        rules=sampled_rules,
                        repair_mode=RepairVariant.EventLevel,
                    )
                )

                time_event = time.perf_counter() - time_event

                fitness_event = fitness_alignment(
                    log,
                    model_event,
                )
                precision_event = precision_alignments_ebi_rust(
                    log,
                    model_event,
                )
                f1_event = (
                    2
                    * fitness_event
                    * precision_event
                    / (fitness_event + precision_event)
                )
                conformance_event = conformance(
                    model_event,
                    sampled_rules,
                    alphabet,
                )

                event_acts = len(get_non_tau_leaves(model_event))

                pm4py.write_ptml(
                    model_event,
                    f"{models_dir}/{eval_id}_e.ptml",
                )

                print(
                    f"Trial {eval_id}: edit-distance model",
                    flush=True,
                )

                time_edit = time.perf_counter()

                model_edit = normalize_tree(
                    apply_IM_with_rules(
                        log,
                        rules=sampled_rules,
                        repair_mode=RepairVariant.EditDistance,
                    )
                )

                time_edit = time.perf_counter() - time_edit

                fitness_edit = fitness_alignment(
                    log,
                    model_edit,
                )
                precision_edit = precision_alignments_ebi_rust(
                    log,
                    model_edit,
                )
                f1_edit = (
                    2 * fitness_edit * precision_edit / (fitness_edit + precision_edit)
                )

                edit_acts = len(get_non_tau_leaves(model_edit))

                conformance_edit = conformance(
                    model_edit,
                    sampled_rules,
                    alphabet,
                )

                pm4py.write_ptml(
                    model_edit,
                    f"{models_dir}/{eval_id}_ed.ptml",
                )

        except TimeoutException:
            print(
                f"Trial {eval_id} timed out, skipping",
                flush=True,
            )
            continue

        except Exception:
            traceback.print_exc()
            continue

        row = {
            "trial": eval_id,
            "num_events": len(log),
            "num_cases": log["case:concept:name"].nunique(),
            "num_rules": len(sampled_rules),
            "num_acts": original_acts,
            "conforming_traces_perc": perc_of_conf_traces,
            "Prepruned_acts": prepruned_acts,
            "Prepruned_Fitness": fitness_prepruned,
            "Prepruned_Precision": precision_prepruned,
            "Prepruned_F1": f1_prepruned,
            "Prepruned_Conformance": conformance_prepruned[0],
            "RIM_NoRepair_acts": norepair_acts,
            "RIM_Fitness_NoRepair": fitness_norepair,
            "RIM_Precision_NoRepair": precision_norepair,
            "RIM_F1_NoRepair": f1_norepair,
            "RIM_Conformance_NoRepair": conformance_norepair[0],
            "RIM_TraceLevel_acts": trace_acts,
            "RIM_Fitness_TraceLevel": fitness_trace,
            "RIM_Precision_TraceLevel": precision_trace,
            "RIM_F1_TraceLevel": f1_trace,
            "RIM_Conformance_TraceLevel": conformance_trace[0],
            "RIM_EventLevel_acts": event_acts,
            "RIM_Fitness_EventLevel": fitness_event,
            "RIM_Precision_EventLevel": precision_event,
            "RIM_F1_EventLevel": f1_event,
            "RIM_Conformance_EventLevel": conformance_event[0],
            "RIM_EditDistance_acts": edit_acts,
            "RIM_Fitness_EditDistance": fitness_edit,
            "RIM_Precision_EditDistance": precision_edit,
            "RIM_F1_EditDistance": f1_edit,
            "RIM_Conformance_EditDistance": conformance_edit[0],
            "Time_Prepruned": time_prepruned,
            "Time_RIM_NoRepair": time_norepair,
            "Time_RIM_TraceLevel": time_trace,
            "Time_RIM_EventLevel": time_event,
            "Time_RIM_Edit": time_edit,
        }

        # Append successful trial to the existing results.
        results = pd.concat(
            [results, pd.DataFrame([row])],
            ignore_index=True,
        )

        completed_ids.add(str(eval_id))

        if "trial" in results.columns:
            # Numeric sorting where possible
            results["_trial_sort"] = pd.to_numeric(
                results["trial"],
                errors="coerce",
            )
            results = (
                results.sort_values(
                    ["_trial_sort", "trial"],
                    na_position="last",
                )
                .drop(columns="_trial_sort")
                .reset_index(drop=True)
            )

        results.to_csv(
            results_path,
            index=False,
        )

    # Final save.
    results.to_csv(
        results_path,
        index=False,
    )

    return results


def save_sm_result(sm_results_path: str, row: dict) -> None:
    """
    Persist exactly one completed trial.

    The function:
      1. reads the current CSV from disk,
      2. replaces/adds this trial,
      3. writes to a temporary file,
      4. atomically replaces the real CSV,
      5. reads the CSV back from disk,
      6. verifies that the trial is actually present.
    """

    sm_results_path = os.path.abspath(sm_results_path)
    os.makedirs(os.path.dirname(sm_results_path), exist_ok=True)

    trial = str(row["trial"])

    # Always reload the current state FROM DISK.
    if os.path.exists(sm_results_path) and os.path.getsize(sm_results_path) > 0:
        current = pd.read_csv(sm_results_path)
    else:
        current = pd.DataFrame()

    # Remove an older version of this same trial, if present.
    if not current.empty and "trial" in current.columns:
        current = current[current["trial"].astype(str) != trial].copy()

    # Add the newly completed trial.
    current = pd.concat(
        [current, pd.DataFrame([row])],
        ignore_index=True,
    )

    # Sort purely for readability.
    current["_trial_sort"] = pd.to_numeric(
        current["trial"],
        errors="coerce",
    )

    current = (
        current.sort_values("_trial_sort", na_position="last")
        .drop(columns="_trial_sort")
        .reset_index(drop=True)
    )

    # Write a complete temporary CSV first.
    directory = os.path.dirname(sm_results_path)

    fd, tmp_path = tempfile.mkstemp(
        prefix="results_sm_",
        suffix=".tmp",
        dir=directory,
    )
    os.close(fd)

    try:
        current.to_csv(
            tmp_path,
            index=False,
        )

        # Replace the destination only after the temporary file
        # has been successfully written.
        os.replace(
            tmp_path,
            sm_results_path,
        )

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # VERIFY WHAT IS ACTUALLY ON DISK.
    written = pd.read_csv(sm_results_path)

    written_trials = set(written["trial"].astype(str))

    if trial not in written_trials:
        raise RuntimeError(
            f"Trial {trial} was written but could not be "
            f"found after reopening {sm_results_path}"
        )

    print(
        f"Trial {trial}: SAVED TO CSV " f"({len(written)} rows) " f"{sm_results_path}",
        flush=True,
    )


def evaluate_split_miner(
    results_path: str = "./experiments/repair_mechanism/results_0.csv",
    sm_results_path: str = "./experiments/repair_mechanism/results_sm.csv",
):
    base_dir = os.path.abspath("./experiments/repair_mechanism")

    models_dir = os.path.join(
        base_dir,
        "models",
    )

    os.makedirs(
        models_dir,
        exist_ok=True,
    )

    results_path = os.path.abspath(results_path)
    sm_results_path = os.path.abspath(sm_results_path)

    print(
        f"Input results:  {results_path}",
        flush=True,
    )

    print(
        f"Output results: {sm_results_path}",
        flush=True,
    )

    print(
        f"Models:         {models_dir}",
        flush=True,
    )

    # ---------------------------------------------------------
    # Load trials that should be evaluated.
    # ---------------------------------------------------------

    original_results = pd.read_csv(results_path)

    if "trial" not in original_results.columns:
        raise ValueError(f"'trial' column missing from {results_path}")

    # ---------------------------------------------------------
    # Determine what is already ACTUALLY ON DISK.
    # ---------------------------------------------------------

    if os.path.exists(sm_results_path) and os.path.getsize(sm_results_path) > 0:
        existing_results = pd.read_csv(sm_results_path)

        if "trial" not in existing_results.columns:
            raise ValueError(f"'trial' column missing from " f"{sm_results_path}")

        completed_ids = set(existing_results["trial"].astype(str))

    else:
        completed_ids = set()

    print(
        f"Already completed: {len(completed_ids)} trials",
        flush=True,
    )

    # ---------------------------------------------------------
    # Evaluate every trial.
    # ---------------------------------------------------------

    for _, result_row in original_results.iterrows():
        input("?//")
        eval_id = result_row["trial"]

        if isinstance(eval_id, float) and eval_id.is_integer():
            eval_id = int(eval_id)

        eval_key = str(eval_id)

        # -----------------------------------------------------
        # Skip trials already present in the CSV on startup.
        # -----------------------------------------------------

        if eval_key in completed_ids:
            print(
                f"Trial {eval_id}: already in CSV, skipping",
                flush=True,
            )
            continue

        print(
            "",
            flush=True,
        )

        print(
            f"========== TRIAL {eval_id} ==========",
            flush=True,
        )

        try:
            # -------------------------------------------------
            # Load event log.
            # -------------------------------------------------

            log_path = os.path.join(
                base_dir,
                "logs",
                f"log_{eval_id}.xes",
            )

            print(
                f"Trial {eval_id}: loading {log_path}",
                flush=True,
            )

            log = pm4py.read_xes(log_path)

            log = log_converter.apply(
                log,
                variant=log_converter.Variants.TO_DATA_FRAME,
            )

            log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

            alphabet = set(log["concept:name"].unique())

            # -------------------------------------------------
            # Load sampled rules.
            # -------------------------------------------------

            rules_path = os.path.join(
                base_dir,
                f"rules_sampled_{eval_id}.txt",
            )

            with open(
                rules_path,
                "r",
                encoding="utf-8",
            ) as file:
                code = file.read()

            lines = []

            for line_number, line in enumerate(
                code.splitlines(),
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                lines.append(f"r{line_number} = {line}")

            code = "\n".join(lines)

            code = re.sub(
                r"\(\s*",
                "('",
                code,
            )

            code = re.sub(
                r"\s*,\s*",
                "', '",
                code,
            )

            code = re.sub(
                r"\s*\)",
                "')",
                code,
            )

            code = f"```python\n" f"{code}\n" f"```"

            _, sampled_rules = code_extraction(
                code,
                activities=list(alphabet),
            )

            if not sampled_rules:
                print(
                    f"Trial {eval_id}: no rules found, skipping",
                    flush=True,
                )
                continue

            # -------------------------------------------------
            # Run the complete evaluation.
            # -------------------------------------------------

            with time_limit(600):

                print(
                    f"Trial {eval_id}: discovering Split Miner",
                    flush=True,
                )

                start_time = time.perf_counter()

                bpmn = pm4py.discover_bpmn_split_miner(log)

                net, im, fm = pm4py.convert_to_petri_net(bpmn)

                time_sm = time.perf_counter() - start_time

                print(
                    f"Trial {eval_id}: Split Miner discovery "
                    f"finished in {time_sm:.3f}s",
                    flush=True,
                )

                # -------------------------------------------------
                # Write model.
                # -------------------------------------------------

                model_path = os.path.join(
                    models_dir,
                    f"{eval_id}_sm.pnml",
                )

                pm4py.write_pnml(
                    net,
                    im,
                    fm,
                    model_path,
                )

                print(
                    f"Trial {eval_id}: model written to " f"{model_path}",
                    flush=True,
                )

                # -------------------------------------------------
                # Fitness.
                # -------------------------------------------------

                print(
                    f"Trial {eval_id}: computing fitness",
                    flush=True,
                )

                fitness_sm = fitness_alignment_pm4py(
                    log,
                    net,
                    im,
                    fm,
                )

                print(
                    f"Trial {eval_id}: fitness = {fitness_sm}",
                    flush=True,
                )

                # -------------------------------------------------
                # Precision.
                # -------------------------------------------------

                print(
                    f"Trial {eval_id}: computing precision",
                    flush=True,
                )

                precision_sm = precision_alignments_ebi_rust_sm(
                    log,
                    (net, im, fm),
                )

                print(
                    f"Trial {eval_id}: precision = " f"{precision_sm}",
                    flush=True,
                )

                # -------------------------------------------------
                # F1.
                # -------------------------------------------------

                if fitness_sm + precision_sm == 0:
                    f1_sm = 0.0
                else:
                    f1_sm = 2 * fitness_sm * precision_sm / (fitness_sm + precision_sm)

                # -------------------------------------------------
                # Rule conformance.
                # -------------------------------------------------

                print(
                    f"Trial {eval_id}: computing conformance",
                    flush=True,
                )

                conformance_sm = conformance(
                    bpmn,
                    sampled_rules,
                    alphabet,
                )

                print(
                    f"Trial {eval_id}: conformance = " f"{conformance_sm[0]}",
                    flush=True,
                )

                # -------------------------------------------------
                # Number of visible activities.
                # -------------------------------------------------

                sm_acts = len(
                    {
                        transition.label
                        for transition in net.transitions
                        if transition.label is not None
                    }
                )

            # =====================================================
            # EVERYTHING ABOVE FINISHED.
            #
            # Construct exactly one final result row.
            # =====================================================

            row = {
                "trial": eval_id,
                "SM_acts": sm_acts,
                "SM_Fitness": fitness_sm,
                "SM_Precision": precision_sm,
                "SM_F1": f1_sm,
                "SM_Conformance": conformance_sm[0],
                "Time_SM": time_sm,
            }

            print(
                f"Trial {eval_id}: evaluation FINISHED",
                flush=True,
            )

            print(
                f"Trial {eval_id}: result = {row}",
                flush=True,
            )

            # =====================================================
            # WRITE THIS RESULT NOW.
            #
            # This function does not return until it has:
            #
            #   - written the CSV
            #   - reopened the CSV
            #   - verified this trial exists in it
            # =====================================================

            save_sm_result(
                sm_results_path,
                row,
            )

            # Only mark it completed AFTER save_sm_result
            # has verified it exists on disk.
            completed_ids.add(eval_key)

            print(
                f"Trial {eval_id}: COMPLETE AND VERIFIED",
                flush=True,
            )

        except TimeoutException:
            print(
                f"Trial {eval_id}: TIMED OUT — NOT WRITTEN",
                flush=True,
            )
            continue

        except Exception:
            print(
                f"Trial {eval_id}: FAILED — NOT WRITTEN",
                flush=True,
            )

            traceback.print_exc()
            continue

    # ---------------------------------------------------------
    # There is deliberately NO final blind to_csv() here.
    #
    # Every successful result was already persisted individually.
    # ---------------------------------------------------------

    if os.path.exists(sm_results_path) and os.path.getsize(sm_results_path) > 0:
        final_results = pd.read_csv(sm_results_path)
    else:
        final_results = pd.DataFrame()

    print(
        "",
        flush=True,
    )

    print(
        f"Finished. CSV contains " f"{len(final_results)} rows:",
        flush=True,
    )

    print(
        sm_results_path,
        flush=True,
    )

    return final_results


if __name__ == "__main__":
    evaluate_split_miner()
