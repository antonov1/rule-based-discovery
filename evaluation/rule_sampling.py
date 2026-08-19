import os
import random
import re
import signal
import time
import traceback
from contextlib import contextmanager
from typing import List, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pm4py
import seaborn as sns
from evaluation.declare_extraction import constraint_based_similarity
from inductive_miner.im_utils import normalize_tree, RepairVariant
from inductive_miner.main import apply_IM_with_rules, preprocess_log as simplify_log
from llm_connection.query import code_extraction
from metrics.fitness import fitness_alignment
from metrics.precision import precision_alignments_ebi_rust
from metrics.rule_conformance import conformance
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.process_tree.obj import ProcessTree
from rule_extraction.from_data import extract


def load_rules(path, alphabet):
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


class TimeoutException(Exception):
    pass


@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException()

    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def get_non_tau_leaves(node: ProcessTree | None) -> Set[str]:
    if node is None:
        return set()

    children = getattr(node, "children", None) or []

    if not children:
        return {node.label} if node.label is not None else set()

    leaves = set()

    for child in children:
        leaves.update(get_non_tau_leaves(child))

    return leaves


def f1(fitness, precision):
    if fitness + precision == 0:
        return 0.0

    return 2 * fitness * precision / (fitness + precision)


def save_rules(rules, path):
    with open(path, "w", encoding="utf-8") as file:
        for rule in rules:
            file.write(f"{rule}\n")


def config_name(support, confidence):
    return f"s_{support:.2f}_c_{confidence:.2f}".replace(".", "_")


def create_heatmap(log_id, rules_by_config, output_dir):
    configs = list(rules_by_config.keys())

    if not configs:
        return

    labels = [f"s={support:.2f}\nc={confidence:.2f}" for support, confidence in configs]

    matrix = np.zeros((len(configs), len(configs)))

    for i, config_a in enumerate(configs):
        for j, config_b in enumerate(configs):
            matrix[i, j] = constraint_based_similarity(
                rules_by_config[config_a],
                rules_by_config[config_b],
            )

    heatmap_df = pd.DataFrame(
        matrix,
        index=labels,
        columns=labels,
    )

    palette = sns.color_palette("colorblind")

    cmap = sns.light_palette(
        palette[0],
        as_cmap=True,
    )

    sns.set_theme(
        style="white",
        context="talk",
        font_scale=0.9,
    )

    fig, ax = plt.subplots(
        figsize=(10, 8),
        dpi=160,
    )

    sns.heatmap(
        heatmap_df,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        vmin=0,
        vmax=1,
        linewidths=1.2,
        linecolor="white",
        cbar_kws={"label": "Constraint-Based Similarity"},
        ax=ax,
    )

    ax.set_title(
        f"Constraint-Based Similarity — {log_id}",
        fontsize=17,
        fontweight="bold",
        pad=14,
    )

    ax.set_xlabel("Support / Confidence")
    ax.set_ylabel("Support / Confidence")

    ax.tick_params(
        axis="x",
        rotation=45,
    )

    ax.tick_params(
        axis="y",
        rotation=0,
    )

    plt.tight_layout()

    plt.savefig(
        f"{output_dir}/{log_id}.png",
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()


def evaluate_model(
    log,
    rules,
    alphabet,
    repair_mode,
    noise_threshold,
):
    start = time.perf_counter()

    model = normalize_tree(
        apply_IM_with_rules(
            log,
            rules=rules,
            repair_mode=repair_mode,
            noise_threshold=noise_threshold,
        )
    )

    runtime = time.perf_counter() - start

    fitness = fitness_alignment(log, model)
    precision = precision_alignments_ebi_rust(log, model)

    return {
        "model": model,
        "acts": len(get_non_tau_leaves(model)),
        "fitness": fitness,
        "precision": precision,
        "f1": f1(fitness, precision),
        "conformance": conformance(
            model,
            rules,
            alphabet,
        )[0],
        "time": runtime,
    }


def evaluate_logs(
    log_paths: List[str],
    parameter_settings: List[Tuple[float, float]],
    timeout_seconds: int = 900,
):
    base_dir = "./experiments/comparison"

    rules_dir = f"{base_dir}/rules"
    models_dir = f"{base_dir}/models"
    heatmaps_dir = f"{base_dir}/heatmaps"
    results_path = f"{base_dir}/results.csv"

    os.makedirs(rules_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(heatmaps_dir, exist_ok=True)

    if os.path.exists(results_path):
        results = pd.read_csv(results_path)
    else:
        results = pd.DataFrame()

    completed = set()

    if not results.empty:
        for _, row in results.iterrows():
            completed.add(
                (
                    str(row["log_id"]),
                    round(float(row["min_support"]), 6),
                    round(float(row["min_confidence"]), 6),
                    round(float(row["noise_threshold"]), 6),
                )
            )

    noise_thresholds = [round(i / 10, 1) for i in range(11)]

    for log_path in log_paths:
        log_id = os.path.splitext(os.path.basename(log_path))[0]

        print(f"\nProcessing {log_id}", flush=True)

        try:
            log = pm4py.read_xes(log_path)

            log = log_converter.apply(
                log,
                variant=log_converter.Variants.TO_DATA_FRAME,
            )

            log["time:timestamp"] = pd.to_datetime(log["time:timestamp"])

            preprocessed_log = simplify_log(log)

            alphabet = set(log["concept:name"].unique())

        except Exception:
            traceback.print_exc()
            continue

        # -----------------------------------------------------
        # Extract rules
        # -----------------------------------------------------

        rules_by_config = {}

        for support, confidence in parameter_settings:
            rule_path = (
                f"{rules_dir}/" f"{log_id}_" f"{config_name(support, confidence)}.txt"
            )

            # -------------------------------------------------
            # Rules already computed -> load them
            # -------------------------------------------------

            if os.path.exists(rule_path):
                print(
                    f"Loading existing rules: "
                    f"support={support}, "
                    f"confidence={confidence}",
                    flush=True,
                )

                try:
                    rules = load_rules(
                        rule_path,
                        alphabet,
                    )

                    rules_by_config[(support, confidence)] = rules

                    continue

                except Exception:
                    print(
                        f"Failed to load rules from {rule_path}; " f"recomputing.",
                        flush=True,
                    )
                    traceback.print_exc()

            # -------------------------------------------------
            # Rules not computed yet -> extract them
            # -------------------------------------------------

            print(
                f"Extracting rules: " f"support={support}, " f"confidence={confidence}",
                flush=True,
            )

            try:
                rules = list(
                    extract(
                        preprocessed_log,
                        min_support=support,
                        min_confidence=confidence,
                        chain_rules=False,
                    )
                )

                if rules:
                    satisfiable = False

                    while not satisfiable:
                        random.seed(42 + len(rules))

                        sample = random.sample(
                            rules,
                            random.randint(
                                1,
                                min(len(rules), 10),
                            ),
                        )

                        log_org = preprocessed_log.copy()

                        for rule in sample:
                            log_org = rule.repair(log_org)

                        if len(log_org) != 0:
                            satisfiable = True
                            rules = sample

                rules_by_config[(support, confidence)] = rules

                save_rules(
                    rules,
                    rule_path,
                )

            except Exception:
                traceback.print_exc()
        create_heatmap(
            log_id,
            rules_by_config,
            heatmaps_dir,
        )

        for (
            support,
            confidence,
        ), rules in rules_by_config.items():

            if not rules:
                continue

            log_copy = preprocessed_log.copy()

            for rule in rules:
                log_copy = rule.apply(log_copy)

            perfectly_fitting_traces_perc = len(log_copy) / len(preprocessed_log) * 100
            for noise_threshold in noise_thresholds:
                key = (
                    str(log_id),
                    round(float(support), 6),
                    round(float(confidence), 6),
                    round(float(noise_threshold), 6),
                )

                if key in completed:
                    print(
                        f"Skipping {key}",
                        flush=True,
                    )
                    continue

                print(
                    f"{log_id} | "
                    f"s={support:.2f} | "
                    f"c={confidence:.2f} | "
                    f"noise={noise_threshold:.1f}",
                    flush=True,
                )

                try:
                    with time_limit(timeout_seconds):
                        naive = evaluate_model(
                            log,
                            rules,
                            alphabet,
                            RepairVariant.Naive,
                            noise_threshold,
                        )

                        edit = evaluate_model(
                            log,
                            rules,
                            alphabet,
                            RepairVariant.EditDistance,
                            noise_threshold,
                        )

                except TimeoutException:
                    print("Timed out", flush=True)
                    continue

                except Exception:
                    traceback.print_exc()
                    continue

                noise_name = f"{noise_threshold:.1f}".replace(".", "_")

                model_prefix = (
                    f"{models_dir}/"
                    f"{log_id}_"
                    f"{config_name(support, confidence)}_"
                    f"noise_{noise_name}"
                )

                pm4py.write_ptml(
                    naive["model"],
                    f"{model_prefix}_naive.ptml",
                )

                pm4py.write_ptml(
                    edit["model"],
                    f"{model_prefix}_edit.ptml",
                )
                row = {
                    "log_id": log_id,
                    "min_support": support,
                    "min_confidence": confidence,
                    "noise_threshold": noise_threshold,
                    "num_events": len(log),
                    "num_cases": log["case:concept:name"].nunique(),
                    "num_rules": len(rules),
                    "perfectly_fitting_traces_perc": perfectly_fitting_traces_perc,
                    "Naive_acts": naive["acts"],
                    "Naive_Fitness": naive["fitness"],
                    "Naive_Precision": naive["precision"],
                    "Naive_F1": naive["f1"],
                    "Naive_Conformance": naive["conformance"],
                    "Naive_Time": naive["time"],
                    "EditDistance_acts": edit["acts"],
                    "EditDistance_Fitness": edit["fitness"],
                    "EditDistance_Precision": edit["precision"],
                    "EditDistance_F1": edit["f1"],
                    "EditDistance_Conformance": edit["conformance"],
                    "EditDistance_Time": edit["time"],
                }

                results = pd.concat(
                    [
                        results,
                        pd.DataFrame([row]),
                    ],
                    ignore_index=True,
                )

                completed.add(key)

                results.to_csv(
                    results_path,
                    index=False,
                )

    if not results.empty:
        results = results.sort_values(
            [
                "log_id",
                "min_support",
                "min_confidence",
                "noise_threshold",
            ]
        ).reset_index(drop=True)

        results.to_csv(
            results_path,
            index=False,
        )

    return results


if __name__ == "__main__":
    log_paths = [
        "./evaluation/data/RTMF.xes",
        "./evaluation/data/SEPSIS.xes",
        "./evaluation/data/BPIC2012.xes",
        "./evaluation/data/BPIC2017.xes",
    ]

    parameter_settings = [
        (1.00, 0.75),  # very frequent rules
        (0.75, 0.50),  # frequent, weaker confidence
        (0.50, 0.50),  # medium support/confidence
        (0.25, 0.75),  # rarer but high-confidence rules
    ]
    evaluate_logs(
        log_paths=log_paths,
        parameter_settings=parameter_settings,
        timeout_seconds=900,
    )
