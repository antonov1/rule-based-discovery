import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import chain, product
from typing import Any, Hashable, Iterator, List, Sequence, Set, Tuple

import pandas as pd
from automata.fa.dfa import DFA
from dotenv import load_dotenv
from inductive_miner.main import preprocess_log
from llm_connection.query import code_extraction, query_llm_for_declare_rules
from promoai.general_utils.llm_connection import LLMConnection
from rules.rule_utils import product_automaton
from scipy.optimize import linear_sum_assignment
from rules import *
import gzip
from typing import Dict, Hashable, Optional

import networkx as nx
import numpy as np
import pm4py
from inductive_miner.im_utils import repair_trace


@dataclass
class EvaluationPrecision:
    original_precision: float
    generated_precision: float
    difference: float


@dataclass
class SlotEvaluation:
    precision: float
    recall: float
    f1_score: float


def shortest_replayable_trace(
    automaton: DFA,
) -> Optional[list[str]]:
    source = automaton.initial_state
    sink = object()

    graph = nx.MultiDiGraph()

    graph.add_nodes_from(automaton.states)
    graph.add_node(sink)

    for state, state_transitions in automaton.transitions.items():
        for symbol, next_state in state_transitions.items():
            graph.add_edge(
                state,
                next_state,
                symbol=symbol,
                weight=1,
            )

    for final_state in automaton.final_states:
        graph.add_edge(
            final_state,
            sink,
            symbol=None,
            weight=0,
        )

    try:
        path = nx.dijkstra_path(
            graph,
            source=source,
            target=sink,
            weight="weight",
        )
    except nx.NetworkXNoPath:
        return None

    trace: list[str] = []

    for current_state, next_state in zip(path, path[1:]):
        edge_data = graph.get_edge_data(current_state, next_state)

        if edge_data is None:
            raise RuntimeError(
                f"Missing edge data for {current_state!r} -> {next_state!r}"
            )

        selected_edge = min(
            edge_data.values(),
            key=lambda data: data["weight"],
        )

        symbol = selected_edge["symbol"]

        if symbol is not None:
            trace.append(symbol)

    return trace


def accepts_trace(trace: Iterable[str], automaton: DFA) -> bool:
    """
    Return True exactly when the DFA accepts the given trace

    """
    state: Hashable = automaton.initial_state

    for symbol in trace:
        if symbol not in automaton.input_symbols:
            return False

        state_transitions = automaton.transitions.get(state)

        if state_transitions is None:
            return False

        next_state = state_transitions.get(symbol)

        if next_state is None:
            return False

        state = next_state

    return state in automaton.final_states


def all_traces_up_to_length(
    k: int,
    alphabet: Set[str],
) -> Iterator[tuple[str, ...]]:
    if k < 0:
        raise ValueError("k must be non-negative")

    symbols = tuple(alphabet)

    return chain.from_iterable(
        product(symbols, repeat=length) for length in range(k + 1)
    )


def declarative_model_precision(
    original_rule_set: Set[AbstractRule],
    generated_rule_set: Set[AbstractRule],
    all_traces: Sequence[Sequence[str]],
    alphabet: Set[str],
) -> EvaluationPrecision:
    original_automata = {
        rule: rule.to_automaton(alphabet) for rule in original_rule_set
    }
    generated_automata = {
        rule: rule.to_automaton(alphabet) for rule in generated_rule_set
    }

    original_product = product_automaton(
        original_rule_set,
        alphabet,
        original_automata,
    )
    generated_product = product_automaton(
        generated_rule_set,
        alphabet,
        generated_automata,
    )

    original_accepted = 0
    generated_accepted = 0
    difference = 0

    for trace in all_traces:
        original_accepts = accepts_trace(trace, original_product)
        generated_accepts = accepts_trace(trace, generated_product)

        original_accepted += int(original_accepts)
        generated_accepted += int(generated_accepts)
        difference += int(original_accepts != generated_accepts)

    num_traces = len(all_traces)

    if num_traces == 0:
        return EvaluationPrecision(
            original_precision=0.0,
            generated_precision=0.0,
            difference=0.0,
        )

    return EvaluationPrecision(
        original_precision=original_accepted / num_traces,
        generated_precision=generated_accepted / num_traces,
        difference=difference / num_traces,
    )


def declarative_model_fitness(
    rule_set: Set[AbstractRule],
    event_log: List[List[str]],
    alphabet: Set[str],
) -> Dict[str, float]:
    automata = {rule: rule.to_automaton(alphabet) for rule in rule_set}
    product = product_automaton(rule_set, alphabet, automata)

    if not product.final_states:
        return {
            "PerfectlyFittingTraces": 0.0,
            "LogFitness": 0.0,
            "AvgTraceFitness": 0.0,
        }

    min_replayable_trace = shortest_replayable_trace(product)
    if min_replayable_trace is None:
        return {
            "PerfectlyFittingTraces": 0.0,
            "LogFitness": 0.0,
            "AvgTraceFitness": 0.0,
        }
    min_replayable_length = len(min_replayable_trace)

    total_cost = 0
    perfectly_fitting = 0
    trace_fitness = []

    for trace in event_log:
        cost = repair_trace(trace, product)["cost"]
        total_cost += cost

        if cost == 0:
            perfectly_fitting += 1

        trace_fitness.append(1 - cost / (min_replayable_length + len(trace)))
    num_events = sum(len(trace) for trace in event_log)
    return {
        "PerfectlyFittingTraces": perfectly_fitting / len(event_log),
        "LogFitness": 1
        - total_cost / (len(event_log) * min_replayable_length + num_events),
        "AvgTraceFitness": float(np.mean(trace_fitness)),
    }


def rule_to_slots(rule: AbstractRule) -> tuple[Any, ...]:
    rule_type = type(rule)

    if hasattr(rule, "target_activity"):
        return (
            rule_type,
            rule.target_activity,
        )

    return (
        rule_type,
        rule.activity_a,
        rule.activity_b,
    )


def constraint_based_similarity(
    original_rules: List[AbstractRule],
    generated_rules: List[AbstractRule],
) -> float:
    slots_org = {rule_to_slots(rule) for rule in original_rules}
    slots_gen = {rule_to_slots(rule) for rule in generated_rules}
    all_rules = slots_org | slots_gen

    if not all_rules:
        return 1.0

    shared_rules = slots_org & slots_gen
    return len(shared_rules) / len(all_rules)


def count_matching_slots(
    gold_slots: Sequence[Any],
    generated_slots: Sequence[Any],
) -> int:
    return sum(
        gold == generated for gold, generated in zip(gold_slots, generated_slots)
    )


def evaluate_slot_filling(
    org_rule_set: List[AbstractRule],
    generated_rule_set: List[AbstractRule],
) -> SlotEvaluation:
    gold_rules = list(org_rule_set)
    generated_rules = list(generated_rule_set)

    gold_slots = [rule_to_slots(rule) for rule in gold_rules]
    generated_slots = [rule_to_slots(rule) for rule in generated_rules]

    if not gold_slots and not generated_slots:
        return SlotEvaluation(
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
        )

    if not gold_slots:
        fp = sum(len(slots) for slots in generated_slots)
        return SlotEvaluation(0.0, 1.0, 0.0)

    if not generated_slots:
        fn = sum(len(slots) for slots in gold_slots)
        return SlotEvaluation(1.0, 0.0, 0.0)

    score_matrix: list[list[int]] = []

    for gold in gold_slots:
        row = []

        for generated in generated_slots:
            if len(gold) != len(generated):
                row.append(0)
            else:
                row.append(count_matching_slots(gold, generated))

        score_matrix.append(row)

    cost_matrix = [[-score for score in row] for row in score_matrix]
    gold_indices, generated_indices = linear_sum_assignment(cost_matrix)

    matched_gold = set()
    matched_generated = set()

    tp = 0
    fp = 0
    fn = 0

    for gold_index, generated_index in zip(
        gold_indices,
        generated_indices,
    ):
        gold = gold_slots[gold_index]
        generated = generated_slots[generated_index]

        matched_gold.add(gold_index)
        matched_generated.add(generated_index)

        if len(gold) != len(generated):
            fp += len(generated)
            fn += len(gold)
            continue

        for gold_slot, generated_slot in zip(gold, generated):
            if gold_slot == generated_slot:
                tp += 1
            else:
                fp += 1
                fn += 1

    for index, slots in enumerate(gold_slots):
        if index not in matched_gold:
            fn += len(slots)

    for index, slots in enumerate(generated_slots):
        if index not in matched_generated:
            fp += len(slots)

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0

    f1_score = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )

    return SlotEvaluation(
        precision=precision,
        recall=recall,
        f1_score=f1_score,
    )


def evaluate(
    process_ids: List[str],
    connection: LLMConnection,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base_dir = "./experiments/declare_extraction"
    model_dir = os.path.join(base_dir, connection.llm_name)
    dataset_dir = "./evaluation/declare_dataset"

    os.makedirs(model_dir, exist_ok=True)

    results_path = os.path.join(model_dir, "results.csv")
    summary_path = os.path.join(model_dir, "summary.csv")

    description_types = ("long",)
    rows: List[dict] = []

    def serialize_rules(
        rules: List[AbstractRule],
    ) -> str:
        return json.dumps(
            [str(rule) for rule in rules],
            ensure_ascii=False,
        )

    def add_fitness_metrics(
        row: dict,
        prefix: str,
        fitness: dict[str, float],
    ) -> None:
        row[f"{prefix}_perfectly_fitting_traces"] = fitness["PerfectlyFittingTraces"]
        row[f"{prefix}_log_fitness"] = fitness["LogFitness"]
        row[f"{prefix}_avg_trace_fitness"] = fitness["AvgTraceFitness"]

    for idx in process_ids:
        json_path = os.path.join(
            dataset_dir,
            f"{idx}.json",
        )
        code_path = os.path.join(
            dataset_dir,
            f"{idx}_code.txt",
        )
        log_path = os.path.join(
            dataset_dir,
            f"{idx}.xes",
        )

        with open(
            json_path,
            encoding="utf-8",
        ) as file:
            process_data = json.load(file)

        with open(
            code_path,
            encoding="utf-8",
        ) as file:
            original_code = file.read()

        alphabet = set(process_data["activities"])

        original_rules = list(
            code_extraction(
                original_code,
                alphabet,
            )[1]
        )

        original_rule_set = set(original_rules)

        event_log = pm4py.read_xes(log_path)
        event_log = pm4py.convert_to_dataframe(event_log)
        if "case:case:concept:name" in event_log.columns:
            event_log.rename(
                columns={"case:case:concept:name": "case:concept:name"},
                inplace=True,
            )
        event_log = preprocess_log(event_log)

        if not event_log:
            raise ValueError(
                f"Event log for process {idx} is empty " "after preprocessing."
            )

        max_trace_length = min(max(len(trace) for trace in event_log), 10)

        path_all_traces = os.path.join(
            dataset_dir,
            f"{idx}_all_traces.json.gz",
        )

        if not os.path.exists(path_all_traces):
            all_traces = list(
                all_traces_up_to_length(
                    max_trace_length,
                    alphabet,
                )
            )

            with gzip.open(
                path_all_traces,
                "wt",
                encoding="utf-8",
            ) as file:
                json.dump(
                    [list(trace) for trace in all_traces],
                    file,
                    ensure_ascii=False,
                )
        else:
            with gzip.open(
                path_all_traces,
                "rt",
                encoding="utf-8",
            ) as file:
                all_traces = [tuple(trace) for trace in json.load(file)]
        original_fitness = declarative_model_fitness(
            original_rule_set,
            event_log,
            alphabet,
        )

        for description_type in description_types:
            description = process_data[description_type]

            row = {
                "process_id": idx,
                "description_type": description_type,
                "description_length": len(description),
                "description_word_count": len(description.split()),
                "alphabet_size": len(alphabet),
                "original_rule_count": len(original_rules),
                "generated_rule_count": pd.NA,
                "original_rules": serialize_rules(original_rules),
                "generated_rules": pd.NA,
                "attempts": pd.NA,
                "original_language_coverage": pd.NA,
                "generated_language_coverage": pd.NA,
                "language_difference": pd.NA,
                "constraint_based_similarity": pd.NA,
                "slot_precision": pd.NA,
                "slot_recall": pd.NA,
                "slot_f1": pd.NA,
                "original_perfectly_fitting_traces": pd.NA,
                "original_log_fitness": pd.NA,
                "original_avg_trace_fitness": pd.NA,
                "generated_perfectly_fitting_traces": pd.NA,
                "generated_log_fitness": pd.NA,
                "generated_avg_trace_fitness": pd.NA,
                "error": pd.NA,
            }

            add_fitness_metrics(
                row,
                prefix="original",
                fitness=original_fitness,
            )

            try:
                (
                    generated_rules,
                    attempts,
                    generated_code,
                ) = query_llm_for_declare_rules(
                    description,
                    alphabet,
                    connection,
                )

                generated_rules = list(generated_rules)
                generated_rule_set = set(generated_rules)

                generated_code_path = os.path.join(
                    model_dir,
                    f"{idx}_code_{description_type}.txt",
                )

                with open(
                    generated_code_path,
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(f"```python\n" f"{generated_code}\n" f"```")

                row["generated_rule_count"] = len(generated_rules)
                row["generated_rules"] = serialize_rules(generated_rules)
                row["attempts"] = attempts + 1

                # Language-based behavioral coverage
                language_result = declarative_model_precision(
                    original_rule_set,
                    generated_rule_set,
                    all_traces,
                    alphabet,
                )

                row["original_language_coverage"] = language_result.original_precision
                row["generated_language_coverage"] = language_result.generated_precision
                row["language_difference"] = language_result.difference

                # Log-based fitness
                generated_fitness = declarative_model_fitness(
                    generated_rule_set,
                    event_log,
                    alphabet,
                )

                add_fitness_metrics(
                    row,
                    prefix="generated",
                    fitness=generated_fitness,
                )

                #  Constraint-set similarity
                row["constraint_based_similarity"] = constraint_based_similarity(
                    original_rules,
                    generated_rules,
                )

                # Slot-level evaluation
                slot_result = evaluate_slot_filling(
                    original_rules,
                    generated_rules,
                )

                row["slot_precision"] = slot_result.precision
                row["slot_recall"] = slot_result.recall
                row["slot_f1"] = slot_result.f1_score

            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"

            rows.append(row)

            slot_f1 = row["slot_f1"]
            generated_avg_fitness = row["generated_avg_trace_fitness"]
            language_difference = row["language_difference"]

            slot_text = f"{float(slot_f1):.3f}" if pd.notna(slot_f1) else "N/A"
            fitness_text = (
                f"{float(generated_avg_fitness):.3f}"
                if pd.notna(generated_avg_fitness)
                else "N/A"
            )
            difference_text = (
                f"{float(language_difference):.3f}"
                if pd.notna(language_difference)
                else "N/A"
            )

            print(
                f"{idx} [{description_type}] "
                f"slot F1={slot_text}, "
                f"generated fitness={fitness_text}, "
                f"language difference={difference_text}"
            )

    results_df = pd.DataFrame(rows)

    numeric_columns = [
        "description_length",
        "description_word_count",
        "alphabet_size",
        "original_rule_count",
        "generated_rule_count",
        "attempts",
        "original_language_coverage",
        "generated_language_coverage",
        "language_difference",
        "constraint_based_similarity",
        "slot_precision",
        "slot_recall",
        "slot_f1",
        "original_perfectly_fitting_traces",
        "original_log_fitness",
        "original_avg_trace_fitness",
        "generated_perfectly_fitting_traces",
        "generated_log_fitness",
        "generated_avg_trace_fitness",
    ]

    for column in numeric_columns:
        results_df[column] = pd.to_numeric(
            results_df[column],
            errors="coerce",
        )

    results_df["description_type"] = pd.Categorical(
        results_df["description_type"],
        categories=list(description_types),
        ordered=True,
    )

    results_df = results_df.sort_values(
        [
            "process_id",
            "description_type",
        ]
    ).reset_index(drop=True)

    results_df.to_csv(
        results_path,
        index=False,
    )

    summary_df = (
        results_df.groupby(
            "description_type",
            observed=True,
        )
        .agg(
            process_count=(
                "process_id",
                "count",
            ),
            successful_count=(
                "slot_f1",
                lambda values: values.notna().sum(),
            ),
            error_count=(
                "error",
                lambda values: values.notna().sum(),
            ),
            average_description_length=(
                "description_length",
                "mean",
            ),
            average_word_count=(
                "description_word_count",
                "mean",
            ),
            average_alphabet_size=(
                "alphabet_size",
                "mean",
            ),
            average_original_rule_count=(
                "original_rule_count",
                "mean",
            ),
            average_generated_rule_count=(
                "generated_rule_count",
                "mean",
            ),
            average_attempts=(
                "attempts",
                "mean",
            ),
            # Language-based evaluation
            original_language_coverage=(
                "original_language_coverage",
                "mean",
            ),
            generated_language_coverage=(
                "generated_language_coverage",
                "mean",
            ),
            language_difference=(
                "language_difference",
                "mean",
            ),
            language_difference_std=(
                "language_difference",
                "std",
            ),
            # Constraint-based evaluation
            constraint_based_similarity=(
                "constraint_based_similarity",
                "mean",
            ),
            constraint_based_similarity_std=(
                "constraint_based_similarity",
                "std",
            ),
            # Slot-based evaluation
            slot_precision=(
                "slot_precision",
                "mean",
            ),
            slot_recall=(
                "slot_recall",
                "mean",
            ),
            slot_f1=(
                "slot_f1",
                "mean",
            ),
            slot_f1_std=(
                "slot_f1",
                "std",
            ),
            # Original-model fitness
            original_perfectly_fitting_traces=(
                "original_perfectly_fitting_traces",
                "mean",
            ),
            original_log_fitness=(
                "original_log_fitness",
                "mean",
            ),
            original_avg_trace_fitness=(
                "original_avg_trace_fitness",
                "mean",
            ),
            # Generated-model fitness
            generated_perfectly_fitting_traces=(
                "generated_perfectly_fitting_traces",
                "mean",
            ),
            generated_perfectly_fitting_traces_std=(
                "generated_perfectly_fitting_traces",
                "std",
            ),
            generated_log_fitness=(
                "generated_log_fitness",
                "mean",
            ),
            generated_log_fitness_std=(
                "generated_log_fitness",
                "std",
            ),
            generated_avg_trace_fitness=(
                "generated_avg_trace_fitness",
                "mean",
            ),
            generated_avg_trace_fitness_std=(
                "generated_avg_trace_fitness",
                "std",
            ),
        )
        .reset_index()
        .round(4)
    )

    summary_df.to_csv(
        summary_path,
        index=False,
    )

    print(f"Detailed results saved to: " f"{results_path}")
    print(f"Summary saved to: " f"{summary_path}")

    return results_df, summary_df


if __name__ == "__main__":
    eval_ids = [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "19",
        "20",
    ]
    load_dotenv(".env", override=True)
    connections = [
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "granite4.1:30b",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "qwen3.6:35b-a3b",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "qwen3.5:9b",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "llama4:latest",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "mistral:7b",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "mistral-medium-3.5:latest",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "laguna-s-2.1:latest",
            "Azure",
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.4-mini", "OpenAI", {}),
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.6-luna", "OpenAI", {}),
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.4", "OpenAI", {}),
    ]

    for connection in connections:
        evaluate(eval_ids, connection)
