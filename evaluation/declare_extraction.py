from dataclasses import dataclass
from typing import Any, List, Sequence, Set, Tuple
from rules import *
import json
import os

import pandas as pd
from automata.fa.dfa import DFA
from dotenv import load_dotenv
from llm_connection.query import code_extraction, query_llm_for_declare_rules
from promoai.general_utils.ai_providers import AIProviders
from promoai.general_utils.llm_connection import LLMConnection
from rules.rule_utils import is_redundant, product_automaton
from scipy.optimize import linear_sum_assignment


@dataclass
class SlotEvaluation:
    precision: float
    recall: float
    f1_score: float


@dataclass
class SemanticEvaluation:
    precision: float
    recall: float
    f1: float
    unsupported_generated_rules: List[AbstractRule]
    unsatisfied_original_rules: List[AbstractRule]


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


def semantic_based_similarity(
    original_rules: List[AbstractRule],
    generated_rules: List[AbstractRule],
    alphabet: Set[str],
) -> SemanticEvaluation:
    all_rules = set(original_rules + generated_rules)
    automata = {rule: rule.to_automaton(alphabet) for rule in all_rules}

    accept_all = DFA.universal_language(input_symbols=set(alphabet))

    unsatisfied_original_rules = [
        rule
        for rule in original_rules
        if not is_redundant(
            rule,
            generated_rules,
            alphabet,
            accept_all,
            automata,
        )
    ]
    generated_product = product_automaton(generated_rules, alphabet, automata)
    if not generated_product.final_states:
        raise ValueError(
            "Generated rule set is unsatisfiable; semantic recall is undefined."
        )
    unsupported_generated_rules = [
        rule
        for rule in generated_rules
        if not is_redundant(
            rule,
            original_rules,
            alphabet,
            accept_all,
            automata,
        )
    ]

    recall = (
        (len(original_rules) - len(unsatisfied_original_rules)) / len(original_rules)
        if original_rules
        else 1.0
    )

    precision = (
        (len(generated_rules) - len(unsupported_generated_rules)) / len(generated_rules)
        if generated_rules
        else 1.0
    )

    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return SemanticEvaluation(
        precision=precision,
        recall=recall,
        f1=f1,
        unsupported_generated_rules=unsupported_generated_rules,
        unsatisfied_original_rules=unsatisfied_original_rules,
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

    description_types = ("long", "med", "short")
    rows: List[dict] = []

    def serialize_rules(rules: List[AbstractRule]) -> str:
        return json.dumps(
            [str(rule) for rule in rules],
            ensure_ascii=False,
        )

    for idx in process_ids:
        json_path = os.path.join(dataset_dir, f"{idx}.json")
        code_path = os.path.join(dataset_dir, f"{idx}_code.txt")

        with open(json_path, encoding="utf-8") as file:
            process_data = json.load(file)

        with open(code_path, encoding="utf-8") as file:
            code = file.read()

        alphabet = set(process_data["activities"])
        original_rules = list(code_extraction(code, alphabet)[1])

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
                "attempts": pd.NA,
                "slot_precision": pd.NA,
                "slot_recall": pd.NA,
                "slot_f1": pd.NA,
                "semantic_precision": pd.NA,
                "semantic_recall": pd.NA,
                "semantic_f1": pd.NA,
                "generated_satisfiable": pd.NA,
                "unsupported_generated_rules": pd.NA,
                "unsatisfied_original_rules": pd.NA,
                "error": pd.NA,
            }

            try:
                generated_rules, attempts, code = query_llm_for_declare_rules(
                    description,
                    alphabet,
                    connection,
                )

                generated_rules = list(generated_rules)
                with open(
                    f"{model_dir}/" f"{idx}_code_{description_type}.txt",
                    "w",
                ) as file:
                    file.write(f"```python\n{code}\n```")

                row["generated_rule_count"] = len(generated_rules)
                row["attempts"] = attempts + 1
                slot_result = evaluate_slot_filling(
                    original_rules,
                    generated_rules,
                )

                row["slot_precision"] = slot_result.precision
                row["slot_recall"] = slot_result.recall
                row["slot_f1"] = slot_result.f1_score

                try:
                    semantic_result = semantic_based_similarity(
                        original_rules,
                        generated_rules,
                        alphabet,
                    )

                    row["generated_satisfiable"] = True
                    row["semantic_precision"] = semantic_result.precision
                    row["semantic_recall"] = semantic_result.recall
                    row["semantic_f1"] = semantic_result.f1
                    row["unsupported_generated_rules"] = serialize_rules(
                        semantic_result.unsupported_generated_rules
                    )
                    row["unsatisfied_original_rules"] = serialize_rules(
                        semantic_result.unsatisfied_original_rules
                    )

                except ValueError as exc:
                    row["generated_satisfiable"] = False
                    row["error"] = f"{type(exc).__name__}: {exc}"

            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"

            rows.append(row)

            slot_f1 = row["slot_f1"]
            semantic_f1 = row["semantic_f1"]

            slot_text = f"{float(slot_f1):.3f}" if pd.notna(slot_f1) else "N/A"
            semantic_text = (
                f"{float(semantic_f1):.3f}" if pd.notna(semantic_f1) else "N/A"
            )

            print(
                f"{idx} [{description_type}] "
                f"slot F1={slot_text}, "
                f"semantic F1={semantic_text}"
            )

    results_df = pd.DataFrame(rows)

    numeric_columns = [
        "description_length",
        "description_word_count",
        "alphabet_size",
        "original_rule_count",
        "generated_rule_count",
        "attempts",
        "slot_precision",
        "slot_recall",
        "slot_f1",
        "semantic_precision",
        "semantic_recall",
        "semantic_f1",
    ]

    for column in numeric_columns:
        results_df[column] = pd.to_numeric(
            results_df[column],
            errors="coerce",
        )

    results_df["generated_satisfiable"] = results_df["generated_satisfiable"].astype(
        "boolean"
    )

    description_order = ["long", "med", "short"]
    results_df["description_type"] = pd.Categorical(
        results_df["description_type"],
        categories=description_order,
        ordered=True,
    )

    results_df = results_df.sort_values(["process_id", "description_type"]).reset_index(
        drop=True
    )

    results_df.to_csv(results_path, index=False)

    summary_df = (
        results_df.groupby(
            "description_type",
            observed=True,
        )
        .agg(
            process_count=("process_id", "count"),
            successful_count=(
                "slot_f1",
                lambda values: values.notna().sum(),
            ),
            satisfiable_count=(
                "generated_satisfiable",
                lambda values: values.eq(True).sum(),
            ),
            average_description_length=(
                "description_length",
                "mean",
            ),
            average_word_count=(
                "description_word_count",
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
            average_attempts=("attempts", "mean"),
            slot_precision=("slot_precision", "mean"),
            slot_recall=("slot_recall", "mean"),
            slot_f1=("slot_f1", "mean"),
            slot_f1_std=("slot_f1", "std"),
            semantic_precision=("semantic_precision", "mean"),
            semantic_recall=("semantic_recall", "mean"),
            semantic_f1=("semantic_f1", "mean"),
            semantic_f1_std=("semantic_f1", "std"),
        )
        .reset_index()
        .round(4)
    )

    summary_df.to_csv(summary_path, index=False)

    paired_slot_f1 = results_df.pivot(
        index="process_id",
        columns="description_type",
        values="slot_f1",
    )

    paired_semantic_f1 = results_df.pivot(
        index="process_id",
        columns="description_type",
        values="semantic_f1",
    )

    for left, right in (
        ("long", "med"),
        ("long", "short"),
        ("med", "short"),
    ):
        if left in paired_slot_f1 and right in paired_slot_f1:
            summary_df[f"slot_{left}_minus_{right}"] = (
                paired_slot_f1[left] - paired_slot_f1[right]
            ).mean()

        if left in paired_semantic_f1 and right in paired_semantic_f1:
            summary_df[f"semantic_{left}_minus_{right}"] = (
                paired_semantic_f1[left] - paired_semantic_f1[right]
            ).mean()

    summary_df.to_csv(summary_path, index=False)

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
        "16",
        "19",
        "20",
    ]
    load_dotenv(".env")
    connections = [
        LLMConnection(os.getenv("OPENAI_API_KEY"), "gpt-5.4-mini", "OpenAI", {}),
        LLMConnection(os.getenv("OPENAI_API_KEY", "gpt-5.4", "OpenAI", {})),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "granite4.1:30b",
            AIProviders.AZURE,
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "qwen3.6:35b-a3b",
            AIProviders.AZURE,
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "qwen3.5:9b",
            AIProviders.AZURE,
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "llama4:latest",
            AIProviders.AZURE,
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
        LLMConnection(
            os.getenv("AZURE_ONE_KEY"),
            "mistral:7b",
            AIProviders.AZURE,
            {"END_POINT": os.getenv("AZURE_ONE_ENDPOINT")},
        ),
    ]
    for connection in connections:
        evaluate(eval_ids, connection)
