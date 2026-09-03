import multiprocessing as mp
import os
import signal
import tempfile
import time
import traceback
from collections import deque
from queue import Empty
from typing import Set

import pandas as pd
import pm4py
from inductive_miner.im_utils import normalize_tree, RepairVariant
from inductive_miner.main import apply_IM_with_rules, preprocess_log as simplify_log
from metrics.fitness import fitness_alignment
from metrics.precision import precision_alignments_ebi_rust
from metrics.rule_conformance import conformance
from pm4py.algo.discovery.inductive import algorithm as pm4py_inductive_miner
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.process_tree.obj import ProcessTree
from rule_extraction.from_data import extract

BASE_DIR = "./experiments/repair_mechanism"
LOGS_DIR = f"{BASE_DIR}/logs"
MODELS_DIR = f"{BASE_DIR}/models"

RESULTS_PATH = f"{BASE_DIR}/results_noise_0.2.csv"

NUM_TRIALS = 200
MAX_WORKERS = 8
TRIAL_TIMEOUT = 600
TERMINATION_GRACE = 5
INITIAL_SEED = 42
MAX_ATTEMPTS_PER_TRIAL = None
SUPERVISOR_POLL_INTERVAL = 0.25

NOISE_THRESHOLD = 0.2


def get_non_tau_leaves(node: ProcessTree | None) -> Set[str]:
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


def safe_f1(fitness: float, precision: float) -> float:
    denominator = fitness + precision

    if denominator == 0:
        return 0.0

    return 2 * fitness * precision / denominator


def traces_to_dataframe(traces) -> pd.DataFrame:
    rows = []
    timestamp = 0

    for case_idx, trace in enumerate(traces):
        case_id = f"prepruned_case_{case_idx}"

        for activity in trace:
            rows.append(
                {
                    "case:concept:name": case_id,
                    "concept:name": activity,
                    "time:timestamp": (
                        pd.Timestamp("2026-01-01") + pd.Timedelta(seconds=timestamp)
                    ),
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


def save_result(results_path: str, row: dict) -> None:
    results_path = os.path.abspath(results_path)
    os.makedirs(os.path.dirname(results_path), exist_ok=True)

    trial = str(row["trial"])

    if os.path.exists(results_path) and os.path.getsize(results_path) > 0:
        current = pd.read_csv(results_path)
    else:
        current = pd.DataFrame()

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

    written = pd.read_csv(results_path)

    written_trials = set(written["trial"].astype(str))

    if trial not in written_trials:
        raise RuntimeError(
            f"Trial {trial} could not be found after " f"writing {results_path}"
        )

    print(
        f"Trial {trial}: SAVED " f"({len(written)} completed trials)",
        flush=True,
    )


def evaluate_process_tree_model(
    log,
    model,
    sampled_rules,
    alphabet,
):
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


def load_existing_log(trial_id: int) -> pd.DataFrame:
    log_path = os.path.join(
        LOGS_DIR,
        f"log_{trial_id}.xes",
    )

    if not os.path.exists(log_path):
        raise FileNotFoundError(
            f"Existing log not found for trial " f"{trial_id}: {log_path}"
        )

    print(
        f"Trial {trial_id}: loading existing log",
        flush=True,
    )

    event_log = pm4py.read_xes(log_path)

    log = log_converter.apply(
        event_log,
        variant=log_converter.Variants.TO_DATA_FRAME,
    )

    log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

    return log


def load_existing_rules(
    trial_id: int,
    preprocessed_log,
):
    """
    Reconstruct the exact sampled rules stored by the original
    experiment.

    The original experiment stored each sampled rule using:

        file.write(f"{rule}\\n")

    Therefore we re-extract the candidate rules from the same
    existing log and select the rules whose string representations
    occur in rules_sampled_<trial>.txt.
    """

    rules_path = os.path.join(
        BASE_DIR,
        f"rules_sampled_{trial_id}.txt",
    )

    if not os.path.exists(rules_path):
        raise FileNotFoundError(
            f"Existing sampled-rules file not found "
            f"for trial {trial_id}: {rules_path}"
        )

    with open(
        rules_path,
        "r",
        encoding="utf-8",
    ) as file:
        sampled_rule_strings = [line.strip() for line in file if line.strip()]

    if not sampled_rule_strings:
        raise RuntimeError(f"Rules file for trial {trial_id} is empty")

    all_rules = extract(
        preprocessed_log,
        min_support=0.25,
        min_confidence=0.5,
    )

    if not all_rules:
        raise RuntimeError(f"No rules could be re-extracted " f"for trial {trial_id}")

    rules_by_string = {}

    for rule in all_rules:
        rule_string = str(rule)

        rules_by_string.setdefault(
            rule_string,
            [],
        ).append(rule)

    sampled_rules = []

    for rule_string in sampled_rule_strings:
        candidates = rules_by_string.get(rule_string)

        if not candidates:
            raise RuntimeError(
                f"Could not reconstruct sampled rule "
                f"for trial {trial_id}: "
                f"{rule_string!r}"
            )

        sampled_rules.append(candidates.pop(0))

    print(
        f"Trial {trial_id}: loaded " f"{len(sampled_rules)} sampled rules",
        flush=True,
    )

    return sampled_rules


def evaluate_trial(
    current_idx: int,
    attempt: int = 0,
    initial_seed: int = INITIAL_SEED,
) -> dict | None:

    try:
        print("", flush=True)

        print(
            f"========== TRIAL {current_idx} | " f"ATTEMPT {attempt + 1} ==========",
            flush=True,
        )

        # ============================================================
        # LOAD ALREADY GENERATED LOG
        # ============================================================

        log = load_existing_log(current_idx)

        preprocessed_log = simplify_log(log)

        alphabet = set(log["concept:name"].unique())

        original_acts = len(alphabet)

        # ============================================================
        # LOAD ALREADY SAMPLED RULES
        # ============================================================

        sampled_rules = load_existing_rules(
            trial_id=current_idx,
            preprocessed_log=preprocessed_log,
        )

        # ============================================================
        # CONFORMING TRACE PERCENTAGE
        # ============================================================

        conforming_log = preprocessed_log.copy()

        for rule in sampled_rules:
            conforming_log = rule.apply(conforming_log)

        conforming_traces_perc = len(conforming_log) / len(preprocessed_log) * 100

        # ============================================================
        # PRE-PRUNE LOG
        # ============================================================

        prepruned_log = preprocessed_log.copy()

        for rule in sampled_rules:
            prepruned_log = rule.repair(prepruned_log)

        if len(prepruned_log) == 0:
            raise RuntimeError(
                f"Trial {current_idx}: " f"pre-pruning removed all traces"
            )

        prepruned_df = traces_to_dataframe(prepruned_log)

        if prepruned_df.empty:
            raise RuntimeError(
                f"Trial {current_idx}: " f"pre-pruned DataFrame is empty"
            )

        # ============================================================
        # PM4PY IMF AFTER PRE-PRUNING
        #
        # Important:
        #     variant = Variants.IMf
        #     noise_threshold = 0.2
        # ============================================================

        print(
            f"Trial {current_idx}: "
            f"PM4Py IMf pre-pruning "
            f"(noise_threshold={NOISE_THRESHOLD})",
            flush=True,
        )

        start = time.perf_counter()

        model_im_prepruned = pm4py_inductive_miner.apply(
            prepruned_df,
            variant=(pm4py_inductive_miner.Variants.IMf),
            parameters={
                "noise_threshold": NOISE_THRESHOLD,
            },
        )

        model_im_prepruned = normalize_tree(model_im_prepruned)

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
                (f"{current_idx}_" f"imf_prepruned_" f"noise_0.2.ptml"),
            ),
        )

        # ============================================================
        # RBIM NAIVE
        # noise_threshold = 0.2
        # ============================================================

        print(
            f"Trial {current_idx}: "
            f"RBIM Naive "
            f"(noise_threshold={NOISE_THRESHOLD})",
            flush=True,
        )

        start = time.perf_counter()

        model_naive = normalize_tree(
            apply_IM_with_rules(
                log,
                rules=sampled_rules,
                repair_mode=RepairVariant.Naive,
                noise_threshold=NOISE_THRESHOLD,
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
                (f"{current_idx}_" f"naive_noise_0.2.ptml"),
            ),
        )

        # ============================================================
        # RBIM TRACE LEVEL
        # noise_threshold = 0.2
        # ============================================================

        print(
            f"Trial {current_idx}: "
            f"RBIM TraceLevel "
            f"(noise_threshold={NOISE_THRESHOLD})",
            flush=True,
        )

        start = time.perf_counter()

        model_trace = normalize_tree(
            apply_IM_with_rules(
                log,
                rules=sampled_rules,
                repair_mode=RepairVariant.TraceLevel,
                noise_threshold=NOISE_THRESHOLD,
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
                (f"{current_idx}_" f"trace_noise_0.2.ptml"),
            ),
        )

        # ============================================================
        # RBIM EVENT LEVEL
        # noise_threshold = 0.2
        # ============================================================

        print(
            f"Trial {current_idx}: "
            f"RBIM EventLevel "
            f"(noise_threshold={NOISE_THRESHOLD})",
            flush=True,
        )

        start = time.perf_counter()

        model_event = normalize_tree(
            apply_IM_with_rules(
                log,
                rules=sampled_rules,
                repair_mode=RepairVariant.EventLevel,
                noise_threshold=NOISE_THRESHOLD,
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
                (f"{current_idx}_" f"event_noise_0.2.ptml"),
            ),
        )

        # ============================================================
        # RBIM EDIT DISTANCE
        # noise_threshold = 0.2
        # ============================================================

        print(
            f"Trial {current_idx}: "
            f"RBIM EditDistance "
            f"(noise_threshold={NOISE_THRESHOLD})",
            flush=True,
        )

        start = time.perf_counter()

        model_edit = normalize_tree(
            apply_IM_with_rules(
                log,
                rules=sampled_rules,
                repair_mode=RepairVariant.EditDistance,
                noise_threshold=NOISE_THRESHOLD,
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
                (f"{current_idx}_" f"edit_noise_0.2.ptml"),
            ),
        )

        # ============================================================
        # RESULT
        # ============================================================

        row = {
            "trial": current_idx,
            "attempt": attempt + 1,
            "noise_threshold": NOISE_THRESHOLD,
            "num_events": len(log),
            "num_cases": log["case:concept:name"].nunique(),
            "num_rules": len(sampled_rules),
            "num_acts": original_acts,
            "conforming_traces_perc": conforming_traces_perc,
            # --------------------------------------------------------
            # IMf + PREPRUNING
            # --------------------------------------------------------
            "IM_Prepruned_acts": im_prepruned["acts"],
            "IM_Prepruned_Fitness": im_prepruned["fitness"],
            "IM_Prepruned_Precision": im_prepruned["precision"],
            "IM_Prepruned_F1": im_prepruned["f1"],
            "IM_Prepruned_Conformance": im_prepruned["conformance"],
            "Time_IM_Prepruned": time_im_prepruned,
            # --------------------------------------------------------
            # RBIM NAIVE
            # --------------------------------------------------------
            "RIM_Naive_acts": naive["acts"],
            "RIM_Naive_Fitness": naive["fitness"],
            "RIM_Naive_Precision": naive["precision"],
            "RIM_Naive_F1": naive["f1"],
            "RIM_Naive_Conformance": naive["conformance"],
            "Time_RIM_Naive": time_naive,
            # --------------------------------------------------------
            # RBIM TRACE LEVEL
            # --------------------------------------------------------
            "RIM_TraceLevel_acts": trace["acts"],
            "RIM_TraceLevel_Fitness": trace["fitness"],
            "RIM_TraceLevel_Precision": trace["precision"],
            "RIM_TraceLevel_F1": trace["f1"],
            "RIM_TraceLevel_Conformance": trace["conformance"],
            "Time_RIM_TraceLevel": time_trace,
            # --------------------------------------------------------
            # RBIM EVENT LEVEL
            # --------------------------------------------------------
            "RIM_EventLevel_acts": event["acts"],
            "RIM_EventLevel_Fitness": event["fitness"],
            "RIM_EventLevel_Precision": event["precision"],
            "RIM_EventLevel_F1": event["f1"],
            "RIM_EventLevel_Conformance": event["conformance"],
            "Time_RIM_EventLevel": time_event,
            # --------------------------------------------------------
            # RBIM EDIT DISTANCE
            # --------------------------------------------------------
            "RIM_EditDistance_acts": edit["acts"],
            "RIM_EditDistance_Fitness": edit["fitness"],
            "RIM_EditDistance_Precision": edit["precision"],
            "RIM_EditDistance_F1": edit["f1"],
            "RIM_EditDistance_Conformance": edit["conformance"],
            "Time_RIM_EditDistance": time_edit,
        }

        print(
            f"Trial {current_idx}, " f"attempt {attempt + 1}: COMPLETE",
            flush=True,
        )

        return row

    except Exception as exc:
        print(
            f"Trial {current_idx}, "
            f"attempt {attempt + 1} FAILED: "
            f"{exc}\n"
            f"{traceback.format_exc()}",
            flush=True,
        )

        return None


def trial_process_entry(
    result_queue,
    trial_id: int,
    attempt: int,
    initial_seed: int,
):
    try:
        if os.name == "posix":
            try:
                os.setsid()
            except Exception:
                pass

        row = evaluate_trial(
            current_idx=trial_id,
            attempt=attempt,
            initial_seed=initial_seed,
        )

        result_queue.put(
            {
                "status": ("success" if row is not None else "retry"),
                "row": row,
            }
        )

    except BaseException as exc:
        try:
            result_queue.put(
                {
                    "status": "retry",
                    "row": None,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

        except Exception:
            pass


def terminate_process_tree(
    process: mp.Process,
    grace_seconds: float = TERMINATION_GRACE,
) -> None:
    if not process.is_alive():
        process.join(timeout=0)
        return

    if os.name == "posix":
        try:
            os.killpg(
                process.pid,
                signal.SIGTERM,
            )

        except ProcessLookupError:
            pass

        except Exception:
            try:
                process.terminate()
            except Exception:
                pass

    else:
        try:
            process.terminate()
        except Exception:
            pass

    process.join(timeout=grace_seconds)

    if process.is_alive():
        if os.name == "posix":
            try:
                os.killpg(
                    process.pid,
                    signal.SIGKILL,
                )

            except ProcessLookupError:
                pass

            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        else:
            try:
                process.kill()
            except Exception:
                pass

        process.join(timeout=grace_seconds)


def close_result_queue(
    result_queue,
) -> None:
    try:
        result_queue.cancel_join_thread()
    except Exception:
        pass

    try:
        result_queue.close()
    except Exception:
        pass


def load_completed_ids(
    results_path: str,
) -> set[int]:
    if not os.path.exists(results_path) or os.path.getsize(results_path) == 0:
        return set()

    existing = pd.read_csv(results_path)

    if "trial" not in existing.columns:
        return set()

    return set(
        pd.to_numeric(
            existing["trial"],
            errors="coerce",
        )
        .dropna()
        .astype(int)
    )


def load_results(
    results_path: str,
) -> pd.DataFrame:
    if not os.path.exists(results_path) or os.path.getsize(results_path) == 0:
        return pd.DataFrame()

    results = pd.read_csv(results_path)

    if "trial" in results.columns:
        results = results.sort_values("trial").reset_index(drop=True)

    return results


def validate_existing_trials(
    requested_trials,
):
    missing_logs = []
    missing_rules = []

    for trial_id in requested_trials:
        log_path = os.path.join(
            LOGS_DIR,
            f"log_{trial_id}.xes",
        )

        rules_path = os.path.join(
            BASE_DIR,
            f"rules_sampled_{trial_id}.txt",
        )

        if not os.path.exists(log_path):
            missing_logs.append(trial_id)

        if not os.path.exists(rules_path):
            missing_rules.append(trial_id)

    if missing_logs or missing_rules:
        messages = []

        if missing_logs:
            messages.append("Missing logs for trial IDs: " f"{missing_logs}")

        if missing_rules:
            messages.append(
                "Missing sampled-rule files " "for trial IDs: " f"{missing_rules}"
            )

        raise FileNotFoundError("\n".join(messages))


def evaluate(
    start_idx: int = 0,
    num_trials: int = NUM_TRIALS,
    max_workers: int = MAX_WORKERS,
    results_path: str = RESULTS_PATH,
    trial_timeout: int = TRIAL_TIMEOUT,
    initial_seed: int = INITIAL_SEED,
    max_attempts_per_trial: int | None = MAX_ATTEMPTS_PER_TRIAL,
):
    if num_trials <= 0:
        raise ValueError("num_trials must be greater than 0")

    if max_workers <= 0:
        raise ValueError("max_workers must be greater than 0")

    if trial_timeout <= 0:
        raise ValueError("trial_timeout must be greater than 0")

    os.makedirs(
        BASE_DIR,
        exist_ok=True,
    )

    os.makedirs(
        LOGS_DIR,
        exist_ok=True,
    )

    os.makedirs(
        MODELS_DIR,
        exist_ok=True,
    )

    results_path = os.path.abspath(results_path)

    requested_trials = list(
        range(
            start_idx,
            start_idx + num_trials,
        )
    )

    requested_set = set(requested_trials)

    validate_existing_trials(requested_trials)

    completed_ids = load_completed_ids(results_path)

    completed_requested_ids = completed_ids & requested_set

    remaining_trials = [
        trial_id
        for trial_id in requested_trials
        if trial_id not in completed_requested_ids
    ]

    print("", flush=True)
    print("=" * 60, flush=True)
    print(
        "RBIM / IMF NOISE EXPERIMENT " "ON EXISTING TRIALS",
        flush=True,
    )
    print("=" * 60, flush=True)

    print(
        f"Noise threshold             : " f"{NOISE_THRESHOLD}",
        flush=True,
    )

    print(
        f"Requested existing trials   : " f"{len(requested_trials)}",
        flush=True,
    )

    print(
        f"Already completed           : " f"{len(completed_requested_ids)}",
        flush=True,
    )

    print(
        f"Still required              : " f"{len(remaining_trials)}",
        flush=True,
    )

    print(
        f"Maximum concurrent attempts : " f"{max_workers}",
        flush=True,
    )

    print(
        f"Hard timeout per attempt    : " f"{trial_timeout} seconds",
        flush=True,
    )

    if max_attempts_per_trial is None:
        print(
            "Retry policy                : " "retry until success",
            flush=True,
        )

    else:
        print(
            f"Retry policy                : "
            f"max {max_attempts_per_trial} "
            f"attempts/trial",
            flush=True,
        )

    print("=" * 60, flush=True)

    if not remaining_trials:
        print(
            "All requested trials are " "already complete.",
            flush=True,
        )

        return load_results(results_path)

    if os.name == "posix":
        context = mp.get_context("forkserver")
    else:
        context = mp.get_context("spawn")

    pending = deque(remaining_trials)

    attempts_started = {trial_id: 0 for trial_id in remaining_trials}

    active = {}

    successful_this_run = 0
    failures_this_run = 0
    timeouts_this_run = 0

    try:
        while pending or active:

            while pending and len(active) < max_workers:
                trial_id = pending.popleft()

                attempt = attempts_started[trial_id]

                if (
                    max_attempts_per_trial is not None
                    and attempt >= max_attempts_per_trial
                ):
                    raise RuntimeError(
                        f"Trial {trial_id} failed "
                        f"{attempt} attempts and "
                        f"reached "
                        f"max_attempts_per_trial="
                        f"{max_attempts_per_trial}."
                    )

                attempts_started[trial_id] += 1

                result_queue = context.Queue(maxsize=1)

                process = context.Process(
                    target=trial_process_entry,
                    args=(
                        result_queue,
                        trial_id,
                        attempt,
                        initial_seed,
                    ),
                    name=(f"trial-{trial_id}-" f"attempt-{attempt + 1}"),
                )

                process.start()

                active[trial_id] = {
                    "process": process,
                    "queue": result_queue,
                    "attempt": attempt,
                    "started_at": time.monotonic(),
                }

                print(
                    f"[START] Trial {trial_id}, "
                    f"attempt {attempt + 1}, "
                    f"PID {process.pid} "
                    f"({len(active)}/"
                    f"{max_workers} active)",
                    flush=True,
                )

            finished_trial_ids = []

            for trial_id, info in list(active.items()):
                process = info["process"]
                result_queue = info["queue"]
                attempt = info["attempt"]

                elapsed = time.monotonic() - info["started_at"]

                message = None

                try:
                    message = result_queue.get_nowait()

                except Empty:
                    pass

                except Exception:
                    pass

                if message is not None:
                    process.join(timeout=TERMINATION_GRACE)

                    if process.is_alive():
                        terminate_process_tree(process)

                    close_result_queue(result_queue)

                    status = message.get("status")

                    row = message.get("row")

                    if status == "success" and row is not None:
                        save_result(
                            results_path,
                            row,
                        )

                        successful_this_run += 1

                        total_completed = (
                            len(completed_requested_ids) + successful_this_run
                        )

                        print(
                            f"[SUCCESS] Trial "
                            f"{trial_id} succeeded "
                            f"on attempt "
                            f"{attempt + 1}. "
                            f"Progress: "
                            f"{total_completed}/"
                            f"{num_trials}",
                            flush=True,
                        )

                    else:
                        failures_this_run += 1

                        print(
                            f"[RETRY] Trial "
                            f"{trial_id} failed "
                            f"on attempt "
                            f"{attempt + 1}.",
                            flush=True,
                        )

                        pending.append(trial_id)

                    finished_trial_ids.append(trial_id)

                    continue

                if elapsed >= trial_timeout:
                    timeouts_this_run += 1

                    print(
                        f"[TIMEOUT] Trial "
                        f"{trial_id}, attempt "
                        f"{attempt + 1} "
                        f"exceeded "
                        f"{trial_timeout} seconds. "
                        f"Killing PID "
                        f"{process.pid}.",
                        flush=True,
                    )

                    terminate_process_tree(process)

                    close_result_queue(result_queue)

                    pending.append(trial_id)

                    finished_trial_ids.append(trial_id)

                    continue

                if not process.is_alive():
                    exitcode = process.exitcode

                    try:
                        message = result_queue.get(timeout=0.1)

                    except Empty:
                        message = None

                    except Exception:
                        message = None

                    process.join(timeout=0)

                    close_result_queue(result_queue)

                    if (
                        message is not None
                        and message.get("status") == "success"
                        and message.get("row") is not None
                    ):
                        row = message["row"]

                        save_result(
                            results_path,
                            row,
                        )

                        successful_this_run += 1

                        total_completed = (
                            len(completed_requested_ids) + successful_this_run
                        )

                        print(
                            f"[SUCCESS] Trial "
                            f"{trial_id} succeeded "
                            f"on attempt "
                            f"{attempt + 1}. "
                            f"Progress: "
                            f"{total_completed}/"
                            f"{num_trials}",
                            flush=True,
                        )

                    else:
                        failures_this_run += 1

                        print(
                            f"[CRASH] Trial "
                            f"{trial_id}, attempt "
                            f"{attempt + 1} "
                            f"exited with code "
                            f"{exitcode} without "
                            f"a successful result. "
                            f"RETRY.",
                            flush=True,
                        )

                        pending.append(trial_id)

                    finished_trial_ids.append(trial_id)

            for trial_id in finished_trial_ids:
                active.pop(
                    trial_id,
                    None,
                )

            if active:
                time.sleep(SUPERVISOR_POLL_INTERVAL)

    except KeyboardInterrupt:
        print("", flush=True)

        print(
            "KeyboardInterrupt received. " "Terminating active trial " "processes...",
            flush=True,
        )

        for info in active.values():
            terminate_process_tree(info["process"])

            close_result_queue(info["queue"])

        raise

    except BaseException:
        for info in active.values():
            try:
                terminate_process_tree(info["process"])
            except Exception:
                pass

            try:
                close_result_queue(info["queue"])
            except Exception:
                pass

        raise

    results = load_results(results_path)

    final_completed_ids = set()

    if not results.empty and "trial" in results.columns:
        final_completed_ids = set(
            pd.to_numeric(
                results["trial"],
                errors="coerce",
            )
            .dropna()
            .astype(int)
        )

    missing = [
        trial_id for trial_id in requested_trials if trial_id not in final_completed_ids
    ]

    print("", flush=True)
    print("=" * 60, flush=True)
    print(
        "EXPERIMENT COMPLETE",
        flush=True,
    )
    print("=" * 60, flush=True)

    print(
        f"Noise threshold             : " f"{NOISE_THRESHOLD}",
        flush=True,
    )

    print(
        f"Requested trials            : " f"{num_trials}",
        flush=True,
    )

    print(
        f"Successful during this run  : " f"{successful_this_run}",
        flush=True,
    )

    print(
        f"Failed attempts retried     : " f"{failures_this_run}",
        flush=True,
    )

    print(
        f"Timed-out attempts retried  : " f"{timeouts_this_run}",
        flush=True,
    )

    print(
        f"Missing requested trial IDs : " f"{len(missing)}",
        flush=True,
    )

    print(
        f"Results                     : " f"{results_path}",
        flush=True,
    )

    print("=" * 60, flush=True)

    if missing:
        raise RuntimeError(
            "Experiment supervisor finished "
            "but the following trial IDs "
            f"are missing: {missing}"
        )

    return results


if __name__ == "__main__":
    mp.freeze_support()

    evaluate(
        start_idx=0,
        num_trials=100,
        max_workers=8,
        trial_timeout=600,
        max_attempts_per_trial=None,
    )
