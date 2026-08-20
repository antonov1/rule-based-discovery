import os
import re
import traceback
from typing import Set

import numpy as np
import pandas as pd
import pm4py
from llm_connection.query import code_extraction
from metrics.fitness import fitness_alignment
from metrics.precision import precision_alignments_ebi_rust
from metrics.rule_conformance import conformance
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.process_tree.obj import ProcessTree

# ============================================================
# Configuration
# ============================================================

# Folder containing runtimes.csv, PTML models, and rule files
MODELS_DIR = "./evaluation/imr/models"

# Folder containing RTFM.xes, HB.xes, ...
LOGS_DIR = "./evaluation/data"

RUNTIMES_PATH = os.path.join(
    MODELS_DIR,
    "runtimes.csv",
)

RESULTS_PATH = os.path.join(
    MODELS_DIR,
    "evaluation_results.csv",
)


# ============================================================
# Helpers
# ============================================================


def get_non_tau_leaves(node: ProcessTree | None) -> Set[str]:
    """Return all visible activities in a process tree."""

    if node is None:
        return set()

    children = getattr(node, "children", None) or []

    if not children:
        return {node.label} if node.label is not None else set()

    leaves = set()

    for child in children:
        leaves.update(get_non_tau_leaves(child))

    return leaves


def load_rules(path, alphabet):
    """Load Declare rules from the rule text file."""

    with open(path, "r", encoding="utf-8") as file:
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

    _, rules = code_extraction(
        code,
        activities=list(alphabet),
    )

    return rules


def parse_setting(setting):
    """
    s_0_25_c_0_75
        ->
    support=0.25, confidence=0.75
    """

    match = re.search(
        r"s_(\d+)_(\d+)_c_(\d+)_(\d+)",
        str(setting),
    )

    if not match:
        return np.nan, np.nan

    support = float(f"{match.group(1)}.{match.group(2)}")

    confidence = float(f"{match.group(3)}.{match.group(4)}")

    return support, confidence


def parse_algorithm(model_file):
    """
    imr_HB_s_0_25_c_0_75_0_6.ptml
        ->
    imr
    """

    filename = os.path.basename(str(model_file))

    return filename.split("_", 1)[0]


def find_file(root_dir, filename):
    """Find a file recursively below root_dir."""

    filename = os.path.basename(str(filename))

    for root, _, files in os.walk(root_dir):
        if filename in files:
            return os.path.join(root, filename)

    return None


def find_log(log_id):
    """Find <log_id>.xes in LOGS_DIR."""

    target = f"{log_id}.xes".lower()

    for root, _, files in os.walk(LOGS_DIR):
        for filename in files:
            if filename.lower() == target:
                return os.path.join(root, filename)

    return None


# ============================================================
# Evaluation
# ============================================================


def evaluate_models():

    runtimes = pd.read_csv(RUNTIMES_PATH)

    # --------------------------------------------------------
    # Only successfully generated models
    # --------------------------------------------------------

    runtimes = runtimes[runtimes["status"].astype(str).str.lower().eq("success")].copy()

    print(f"Found {len(runtimes)} successful models.")

    # --------------------------------------------------------
    # Resume previous evaluation
    # --------------------------------------------------------

    if os.path.exists(RESULTS_PATH):
        results = pd.read_csv(RESULTS_PATH)
    else:
        results = pd.DataFrame()

    completed = set()

    if not results.empty:
        completed = set(results["model_file"].astype(str))

    # Cache event logs and rules
    log_cache = {}
    rule_cache = {}

    # --------------------------------------------------------
    # Evaluate models
    # --------------------------------------------------------

    for _, row in runtimes.iterrows():

        model_file = str(row["model_file"])

        if model_file in completed:
            print(f"Skipping {model_file}")
            continue

        log_id = str(row["log"])

        support, confidence = parse_setting(row["setting"])

        sup = pd.to_numeric(
            row["sup"],
            errors="coerce",
        )

        algorithm = parse_algorithm(model_file)

        print(
            f"\n{log_id} | "
            f"{algorithm} | "
            f"s={support:.2f} | "
            f"c={confidence:.2f} | "
            f"sup={sup}"
        )

        try:
            # =================================================
            # Locate files
            # =================================================

            model_path = find_file(
                MODELS_DIR,
                model_file,
            )

            rules_path = find_file(
                MODELS_DIR,
                row["rules_file"],
            )

            if model_path is None:
                raise FileNotFoundError(f"Model not found: {model_file}")

            if rules_path is None:
                raise FileNotFoundError(f"Rules not found: {row['rules_file']}")

            # =================================================
            # Load event log
            # =================================================

            if log_id not in log_cache:

                log_path = find_log(log_id)

                if log_path is None:
                    raise FileNotFoundError(f"Event log not found: {log_id}.xes")

                log = pm4py.read_xes(log_path)

                log = log_converter.apply(
                    log,
                    variant=log_converter.Variants.TO_DATA_FRAME,
                )

                if "time:timestamp" in log.columns:
                    log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

                alphabet = set(log["concept:name"].dropna().unique())

                log_cache[log_id] = (
                    log,
                    alphabet,
                )

            log, alphabet = log_cache[log_id]

            # =================================================
            # Load rules
            # =================================================

            rules_key = (
                log_id,
                os.path.abspath(rules_path),
            )

            if rules_key not in rule_cache:

                rule_cache[rules_key] = load_rules(
                    rules_path,
                    alphabet,
                )

            rules = rule_cache[rules_key]

            # =================================================
            # Load existing PTML model
            # =================================================

            model = pm4py.read_ptml(model_path)

            # =================================================
            # Metrics
            # =================================================

            fitness = fitness_alignment(
                log,
                model,
            )

            precision = precision_alignments_ebi_rust(
                log,
                model,
            )

            num_activities = len(get_non_tau_leaves(model))

            model_conformance = conformance(
                model,
                rules,
                alphabet,
            )[0]

            # =================================================
            # Store result
            # =================================================

            result = {
                "log": log_id,
                "algorithm": algorithm,
                "setting": row["setting"],
                "support": support,
                "confidence": confidence,
                "sup": sup,
                "fitness": fitness,
                "precision": precision,
                "num_activities": num_activities,
                "conformance": model_conformance,
                # Original mining runtime
                "runtime_seconds": pd.to_numeric(
                    row["runtime_seconds"],
                    errors="coerce",
                ),
                "model_file": model_file,
            }

            results = pd.concat(
                [
                    results,
                    pd.DataFrame([result]),
                ],
                ignore_index=True,
            )

            completed.add(model_file)

            # Save immediately so the experiment is resumable
            results.to_csv(
                RESULTS_PATH,
                index=False,
            )

            print(
                f"  fitness      = {fitness:.4f}\n"
                f"  precision    = {precision:.4f}\n"
                f"  activities   = {num_activities}\n"
                f"  conformance  = {model_conformance:.4f}\n"
                f"  runtime      = {row['runtime_seconds']:.2f}s"
            )

        except Exception:
            print(f"FAILED: {model_file}")
            traceback.print_exc()

    # --------------------------------------------------------
    # Final sorting
    # --------------------------------------------------------

    if not results.empty:

        results = results.sort_values(
            [
                "log",
                "algorithm",
                "support",
                "confidence",
                "sup",
            ]
        ).reset_index(drop=True)

        results.to_csv(
            RESULTS_PATH,
            index=False,
        )

    return results


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    results = evaluate_models()

    print(f"\nFinished.\n" f"Results: {RESULTS_PATH}")
