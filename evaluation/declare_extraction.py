import json
import os
from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Hashable, List, Sequence, Set, Tuple

import networkx as nx
import pandas as pd
from automata.fa.dfa import DFA
from dotenv import load_dotenv
from inductive_miner.main import preprocess_log
from llm_connection.query import code_extraction, query_llm_for_declare_rules
from promoai.general_utils.llm_connection import LLMConnection
from rules.rule_utils import product_automaton
from scipy.optimize import linear_sum_assignment
from rules import *
import signal
from typing import Dict, Hashable, Optional

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


class TraceTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise TraceTimeout


signal.signal(signal.SIGALRM, timeout_handler)


def update_results_table(
    old: pd.DataFrame,
    new: pd.DataFrame,
    keys=("process_id", "description_type"),
) -> pd.DataFrame:
    keys = list(keys)

    old = old.copy()
    new = new.copy()

    old["process_id"] = old["process_id"].astype(str).str.zfill(2)
    new["process_id"] = new["process_id"].astype(str).str.zfill(2)

    new_keys = new[keys].drop_duplicates()

    old = old.merge(
        new_keys.assign(_replace=True),
        on=keys,
        how="left",
    )

    old = old[old["_replace"].isna()].drop(columns="_replace")

    return pd.concat(
        [old, new],
        ignore_index=True,
    )


def prefix_of_log(log: List[List[str]]) -> List[List[str]]:
    """Return all non-empty prefixes occurring in the log."""
    return [trace[:i] for trace in log for i in range(1, len(trace) + 1)]


def construct_prefix_automaton(log: List[List[str]]) -> DFA:
    alphabet = {activity for trace in log for activity in trace}

    prefix_to_state = {
        (): "q0",
    }

    states = {"q0"}
    transitions = {"q0": {}}
    final_states = set()

    next_state_number = 1

    for trace in log:
        current_prefix = ()
        current_state = "q0"

        if not trace:
            final_states.add("q0")
            continue

        for activity in trace:
            next_prefix = current_prefix + (activity,)

            if next_prefix not in prefix_to_state:
                next_state = f"q{next_state_number}"
                next_state_number += 1

                prefix_to_state[next_prefix] = next_state
                states.add(next_state)
                transitions[next_state] = {}
            else:
                next_state = prefix_to_state[next_prefix]

            transitions[current_state][activity] = next_state

            current_prefix = next_prefix
            current_state = next_state

        final_states.add(current_state)

    return DFA(
        states=states,
        input_symbols=alphabet,
        transitions=transitions,
        initial_state="q0",
        final_states=final_states,
        allow_partial=True,
    )


def global_escaping_edge_precision(
    log: List[List[str]],
    constraints: List[AbstractRule],
) -> float:
    if not log:
        return 1.0

    prefix_automaton = construct_prefix_automaton(log)
    alphabet = set(prefix_automaton.input_symbols)

    rule_automata = {rule: rule.to_automaton(alphabet) for rule in constraints}

    product = product_automaton(
        constraints,
        alphabet,
        rule_automata,
    )

    if not product.final_states:
        print("Number of final states:", len(product.final_states))
        print("Initial state:", product.initial_state)
        print("Number of product states:", len(product.states))
        return 0.0

    reverse_transitions: Dict[object, Set[object]] = defaultdict(set)

    for source_state, outgoing in product.transitions.items():
        for target_state in outgoing.values():
            reverse_transitions[target_state].add(source_state)

    live_states: Set[object] = set(product.final_states)
    queue = deque(product.final_states)

    while queue:
        state = queue.popleft()

        for predecessor in reverse_transitions.get(state, set()):
            if predecessor not in live_states:
                live_states.add(predecessor)
                queue.append(predecessor)

    if product.initial_state not in live_states:
        return 0.0

    prefix_frequency: Counter[Tuple[str, ...]] = Counter()
    observed_next: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)

    for trace in log:
        clean_trace = [activity for activity in trace if activity in alphabet]

        # Include the empty prefix.
        for index in range(len(clean_trace) + 1):
            prefix = tuple(clean_trace[:index])
            prefix_frequency[prefix] += 1

            if index < len(clean_trace):
                observed_next[prefix].add(clean_trace[index])

    total_enabled = 0
    total_observed_and_enabled = 0

    for prefix, frequency in prefix_frequency.items():
        model_state = product.initial_state
        valid_prefix = True

        for activity in prefix:
            outgoing = product.transitions.get(model_state, {})

            if activity not in outgoing:
                valid_prefix = False
                break

            next_state = outgoing[activity]

            if next_state not in live_states:
                valid_prefix = False
                break

            model_state = next_state

        if not valid_prefix:
            continue

        observed_edges = observed_next.get(prefix, set())

        model_enabled_edges = {
            activity
            for activity, target_state in product.transitions.get(
                model_state, {}
            ).items()
            if target_state in live_states
        }

        total_enabled += frequency * len(model_enabled_edges)

        total_observed_and_enabled += frequency * len(
            observed_edges & model_enabled_edges
        )

    if total_enabled == 0:
        return 1.0

    return total_observed_and_enabled / total_enabled


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
            "Satisfiable": False,
            "PerfectlyFittingTraces": 0.0,
            "LogFitness": 0.0,
            "AvgTraceFitness": 0.0,
            "AvgConstraintConformance": 0.0,
        }

    min_replayable_trace = shortest_replayable_trace(product)
    if min_replayable_trace is None:
        return {
            "Satisfiable": False,
            "PerfectlyFittingTraces": 0.0,
            "LogFitness": 0.0,
            "AvgTraceFitness": 0.0,
            "AvgConstraintConformance": 0.0,
        }
    log_copy = [list(trace) for trace in event_log]
    rule_fitness_values = []
    for rule in rule_set:
        log_copy = rule.apply(log_copy)
        conformance = len(log_copy) / len(event_log) if log_copy else 0.0
        log_copy = [list(trace) for trace in event_log]
        rule_fitness_values.append(conformance)

    min_replayable_length = len(min_replayable_trace)

    total_cost = 0
    perfectly_fitting = 0
    trace_fitness = []
    evaluated_trace_count = 0
    evaluated_event_count = 0
    trace_counts = Counter(tuple(trace) for trace in event_log)

    for trace, count in trace_counts.items():
        try:
            signal.alarm(20)

            if accepts_trace(trace, product):
                cost = 0
            else:
                cost = repair_trace(trace, product)["cost"]

        except TraceTimeout:
            print(f"Trace timed out: {trace}")
            continue  # Skip this trace if it times out

        finally:
            signal.alarm(0)
        evaluated_trace_count += count
        evaluated_event_count += len(trace) * count
        total_cost += cost * count

        if cost == 0:
            perfectly_fitting += count

        fitness = 1 - cost / (min_replayable_length + len(trace))
        trace_fitness.extend([fitness] * count)

    if evaluated_trace_count == 0:
        return {
            "Satisfiable": True,
            "PerfectlyFittingTraces": 0.0,
            "LogFitness": 0.0,
            "AvgTraceFitness": 0.0,
            "AvgConstraintConformance": float(np.mean(rule_fitness_values)),
        }

    return {
        "Satisfiable": True,
        "PerfectlyFittingTraces": perfectly_fitting / evaluated_trace_count,
        "LogFitness": 1
        - total_cost
        / (evaluated_trace_count * min_replayable_length + evaluated_event_count),
        "AvgTraceFitness": float(np.mean(trace_fitness)),
        "AvgConstraintConformance": float(np.mean(rule_fitness_values)),
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
        fitness: dict[str, Any],
    ) -> None:
        row[f"{prefix}_satisfiable"] = fitness["Satisfiable"]
        row[f"{prefix}_perfectly_fitting_traces"] = fitness["PerfectlyFittingTraces"]
        row[f"{prefix}_log_fitness"] = fitness["LogFitness"]
        row[f"{prefix}_avg_trace_fitness"] = fitness["AvgTraceFitness"]
        row[f"{prefix}_avg_constraint_conformance"] = fitness[
            "AvgConstraintConformance"
        ]

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

        if (
            "case:case:concept:name" in event_log.columns
            and "case:concept:name" not in event_log.columns
        ):
            event_log.rename(
                columns={
                    "case:case:concept:name": "case:concept:name",
                },
                inplace=True,
            )

        print(event_log.head(5))

        event_log = preprocess_log(event_log)

        if not event_log:
            raise ValueError(
                f"Event log for process {idx} is empty " "after preprocessing."
            )

        # Original-model evaluation

        original_fitness = declarative_model_fitness(
            original_rule_set,
            event_log,
            alphabet,
        )

        original_precision = global_escaping_edge_precision(
            event_log,
            original_rules,
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
                # Precision
                "original_precision": original_precision,
                "generated_precision": pd.NA,
                # Constraint-set similarity
                "constraint_based_similarity": pd.NA,
                # Slot filling
                "slot_precision": pd.NA,
                "slot_recall": pd.NA,
                "slot_f1": pd.NA,
                # Original fitness
                "original_satisfiable": pd.NA,
                "original_perfectly_fitting_traces": pd.NA,
                "original_log_fitness": pd.NA,
                "original_avg_trace_fitness": pd.NA,
                "original_avg_constraint_conformance": pd.NA,
                # Generated fitness
                "generated_satisfiable": pd.NA,
                "generated_perfectly_fitting_traces": pd.NA,
                "generated_log_fitness": pd.NA,
                "generated_avg_trace_fitness": pd.NA,
                "generated_avg_constraint_conformance": pd.NA,
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

                # Precision

                row["generated_precision"] = global_escaping_edge_precision(
                    event_log,
                    generated_rules,
                )

                # Fitness

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

                # Constraint-based similarity

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
            generated_precision = row["generated_precision"]
            generated_log_fitness = row["generated_log_fitness"]

            slot_text = f"{float(slot_f1):.3f}" if pd.notna(slot_f1) else "N/A"

            precision_text = (
                f"{float(generated_precision):.3f}"
                if pd.notna(generated_precision)
                else "N/A"
            )

            fitness_text = (
                f"{float(generated_log_fitness):.3f}"
                if pd.notna(generated_log_fitness)
                else "N/A"
            )

            print(
                f"{idx} [{description_type}] "
                f"slot F1={slot_text}, "
                f"generated precision={precision_text}, "
                f"generated log fitness={fitness_text}"
            )

    results_df = pd.DataFrame(rows)

    # --------------------------------------------------------
    # Merge rerun results with existing results
    # --------------------------------------------------------

    if os.path.exists(results_path):
        existing_results = pd.read_csv(
            results_path,
            dtype={"process_id": str},
        )

        results_df = update_results_table(
            existing_results,
            results_df,
        )

    # --------------------------------------------------------
    # Normalize numeric columns
    # --------------------------------------------------------

    numeric_columns = [
        "description_length",
        "description_word_count",
        "alphabet_size",
        "original_rule_count",
        "generated_rule_count",
        "attempts",
        # Precision
        "original_precision",
        "generated_precision",
        # Constraint similarity
        "constraint_based_similarity",
        # Slot evaluation
        "slot_precision",
        "slot_recall",
        "slot_f1",
        # Original fitness
        "original_perfectly_fitting_traces",
        "original_log_fitness",
        "original_avg_trace_fitness",
        "original_avg_constraint_conformance",
        # Generated fitness
        "generated_perfectly_fitting_traces",
        "generated_log_fitness",
        "generated_avg_trace_fitness",
        "generated_avg_constraint_conformance",
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

    results_df["process_id"] = results_df["process_id"].astype(str).str.zfill(2)

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

    # --------------------------------------------------------
    # Rebuild summary from complete merged results
    # --------------------------------------------------------

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
            original_precision=(
                "original_precision",
                "mean",
            ),
            original_precision_std=(
                "original_precision",
                "std",
            ),
            generated_precision=(
                "generated_precision",
                "mean",
            ),
            generated_precision_std=(
                "generated_precision",
                "std",
            ),
            constraint_based_similarity=(
                "constraint_based_similarity",
                "mean",
            ),
            constraint_based_similarity_std=(
                "constraint_based_similarity",
                "std",
            ),
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
            original_avg_constraint_conformance=(
                "original_avg_constraint_conformance",
                "mean",
            ),
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
            generated_avg_constraint_conformance=(
                "generated_avg_constraint_conformance",
                "mean",
            ),
            generated_avg_constraint_conformance_std=(
                "generated_avg_constraint_conformance",
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

    print(f"Detailed results saved to: {results_path}")
    print(f"Summary saved to: {summary_path}")

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
        "17",
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
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.4-mini", "OpenAI", {}),
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.6-luna", "OpenAI", {}),
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.4", "OpenAI", {}),
        LLMConnection(
            os.getenv("GOOGLE_API_KEY"), "gemini-3.1-pro-preview", "Google", {}
        ),
        LLMConnection(os.getenv("GOOGLE_API_KEY"), "gemini-3.5-flash", "Google", {}),
    ]

    for connection in connections:
        evaluate(eval_ids, connection)
