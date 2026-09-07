import os
import traceback
from typing import Set

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

EXPERIMENT_DIR = "./experiments/imr"

RUNTIMES_PATH = os.path.join(
    EXPERIMENT_DIR,
    "runtimes.csv",
)

RESULTS_PATH_SUPPORT_1 = os.path.join(
    EXPERIMENT_DIR,
    "evaluation_results_support_1.0.csv",
)

RESULTS_PATH_SUPPORT_08 = os.path.join(
    EXPERIMENT_DIR,
    "evaluation_results_support_0.8.csv",
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
    """Load DECLARE rules from a rule text file."""

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

    import re

    code = re.sub(r"\(\s*", "('", code)
    code = re.sub(r"\s*,\s*", "', '", code)
    code = re.sub(r"\s*\)", "')", code)

    code = f"```python\n{code}\n```"

    _, rules = code_extraction(
        code,
        activities=list(alphabet),
    )

    return rules


def find_file(root_dir, filename):
    """Find a file recursively below root_dir."""

    filename = os.path.basename(str(filename))

    for root, _, files in os.walk(root_dir):
        if filename in files:
            return os.path.join(root, filename)

    return None


def load_existing_results(path):
    """Load an existing evaluation CSV, or return an empty DataFrame."""

    if os.path.exists(path):
        return pd.read_csv(path)

    return pd.DataFrame()


def save_results(results, path):
    """Sort and save evaluation results."""

    if results.empty:
        return

    sort_columns = [
        column
        for column in [
            "trial",
            "support",
            "model_file",
        ]
        if column in results.columns
    ]

    if sort_columns:
        results = results.sort_values(sort_columns).reset_index(drop=True)

    results.to_csv(
        path,
        index=False,
    )


# ============================================================
# Evaluation
# ============================================================


def evaluate_models():

    runtimes = pd.read_csv(RUNTIMES_PATH)

    # --------------------------------------------------------
    # Only successfully generated models
    # --------------------------------------------------------

    runtimes = runtimes[runtimes["status"].astype(str).str.lower().eq("success")].copy()

    runtimes["support"] = pd.to_numeric(
        runtimes["support"],
        errors="coerce",
    )

    # Only evaluate the two expected support settings
    runtimes = runtimes[runtimes["support"].isin([1.0, 0.8])].copy()

    print(f"Found {len(runtimes)} successful models.")

    print(runtimes["support"].value_counts().sort_index())

    # --------------------------------------------------------
    # Resume previous evaluations
    # --------------------------------------------------------

    results_by_support = {
        1.0: load_existing_results(RESULTS_PATH_SUPPORT_1),
        0.8: load_existing_results(RESULTS_PATH_SUPPORT_08),
    }

    completed_by_support = {}

    for support, results in results_by_support.items():

        if results.empty or "model_file" not in results.columns:
            completed_by_support[support] = set()
        else:
            completed_by_support[support] = set(results["model_file"].astype(str))

    # Cache logs and parsed rules
    log_cache = {}
    rule_cache = {}

    # --------------------------------------------------------
    # Evaluate models
    # --------------------------------------------------------

    for _, row in runtimes.iterrows():

        support = float(row["support"])
        trial = int(row["trial"])

        model_file = str(row["model_file"])
        log_file = str(row["log_file"])
        rules_file = str(row["rules_file"])

        if model_file in completed_by_support[support]:
            print(f"Skipping trial {trial}: " f"{model_file}")
            continue

        print(f"\nTrial {trial} | " f"support={support:.1f} | " f"{model_file}")

        try:

            # =================================================
            # Locate files
            # =================================================

            model_path = find_file(
                EXPERIMENT_DIR,
                model_file,
            )

            log_path = find_file(
                EXPERIMENT_DIR,
                log_file,
            )

            rules_path = find_file(
                EXPERIMENT_DIR,
                rules_file,
            )

            if model_path is None:
                raise FileNotFoundError(f"Model not found: {model_file}")

            if log_path is None:
                raise FileNotFoundError(f"Event log not found: {log_file}")

            if rules_path is None:
                raise FileNotFoundError(f"Rules not found: {rules_file}")

            # =================================================
            # Load event log
            # =================================================

            log_key = os.path.abspath(log_path)

            if log_key not in log_cache:

                log = pm4py.read_xes(
                    log_path,
                )

                log = log_converter.apply(
                    log,
                    variant=log_converter.Variants.TO_DATA_FRAME,
                )

                if "time:timestamp" in log.columns:
                    log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

                alphabet = set(log["concept:name"].dropna().unique())

                log_cache[log_key] = (
                    log,
                    alphabet,
                )

            log, alphabet = log_cache[log_key]

            # =================================================
            # Load rules
            # =================================================

            rules_key = (
                os.path.abspath(rules_path),
                frozenset(alphabet),
            )

            if rules_key not in rule_cache:

                rule_cache[rules_key] = load_rules(
                    rules_path,
                    alphabet,
                )

            rules = rule_cache[rules_key]

            # =================================================
            # Load PTML model
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

            runtime_seconds = pd.to_numeric(
                row["runtime_seconds"],
                errors="coerce",
            )

            # =================================================
            # Store result
            # =================================================

            result = {
                "trial": trial,
                "support": support,
                "fitness": fitness,
                "precision": precision,
                "num_activities": num_activities,
                "conformance": model_conformance,
                "runtime_seconds": runtime_seconds,
                "rules_file": rules_file,
                "log_file": log_file,
                "model_file": model_file,
            }

            results = results_by_support[support]

            results = pd.concat(
                [
                    results,
                    pd.DataFrame([result]),
                ],
                ignore_index=True,
            )

            results_by_support[support] = results

            completed_by_support[support].add(model_file)

            # Save immediately so evaluation is resumable
            if support == 1.0:
                output_path = RESULTS_PATH_SUPPORT_1
            else:
                output_path = RESULTS_PATH_SUPPORT_08

            save_results(
                results,
                output_path,
            )

            print(
                f"  fitness      = {fitness:.4f}\n"
                f"  precision    = {precision:.4f}\n"
                f"  activities   = {num_activities}\n"
                f"  conformance  = {model_conformance:.4f}\n"
                f"  runtime      = {runtime_seconds:.4f}s"
            )

        except Exception:

            print(f"FAILED: trial={trial}, " f"model={model_file}")

            traceback.print_exc()

    # --------------------------------------------------------
    # Final sorting / saving
    # --------------------------------------------------------

    save_results(
        results_by_support[1.0],
        RESULTS_PATH_SUPPORT_1,
    )

    save_results(
        results_by_support[0.8],
        RESULTS_PATH_SUPPORT_08,
    )

    return results_by_support


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    results = evaluate_models()

    print("\nFinished.")
    print(f"Support 1.0 results: " f"{RESULTS_PATH_SUPPORT_1}")
    print(f"Support 0.8 results: " f"{RESULTS_PATH_SUPPORT_08}")
