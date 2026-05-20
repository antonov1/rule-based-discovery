import math

import pandas as pd
from pm4py import discover_process_tree_inductive, ProcessTree
from pm4py.objects.log.obj import Event, EventLog, Trace
from pm4py.objects.process_tree.obj import Operator, ProcessTree
from pm4py.objects.process_tree.utils.generic import get_leaves


def find_shortest_replayable_trace_length(
    tree: ProcessTree,
) -> int:
    if tree.label is None and not tree.children:
        # Tau
        return 0
    if tree.label is not None:
        # Activity
        return 1
    if tree.operator == Operator.SEQUENCE or tree.operator == Operator.PARALLEL:
        children = [
            find_shortest_replayable_trace_length(child) for child in tree.children
        ]
        return sum(children)
    elif tree.operator == Operator.XOR:
        # the minimum
        xor = [find_shortest_replayable_trace_length(child) for child in tree.children]
        return min(xor)
    elif tree.operator == Operator.LOOP:
        # the mandatory part only
        return find_shortest_replayable_trace_length(tree.children[0])


def create_trace(labels: list[str], name: str | None = None) -> Trace:
    trace = Trace()
    if name is not None:
        trace.attributes["concept:name"] = name
    for label in labels:
        event = Event()
        event["concept:name"] = label
        trace.append(event)
    return trace


def trace_to_tuple(trace: Trace) -> tuple[str, ...]:
    return tuple(event["concept:name"] for event in trace)


def discover_process_tree(
    event_log: EventLog | pd.DataFrame, noise_threshold: float = 0.25
) -> ProcessTree:
    # Discover process tree using Inductive Miner infrequent
    return discover_process_tree_inductive(event_log, noise_threshold=noise_threshold)


def discover_process_tree_with_naive_label_splitting(
    event_log: pd.DataFrame,
    max_distinction: int = 3,
    noise_threshold: float = 0.25,
) -> ProcessTree:
    if max_distinction < 1:
        raise ValueError("max_distinction must be at least 1.")
    digits = int(math.log10(max_distinction)) + 1

    # Add counts to activity labels
    event_log = event_log.copy()
    if "lifecycle:transition" in event_log.columns:
        event_log.sort_values(
            [
                "case:concept:name",
                "time:timestamp",
                "concept:name",
                "lifecycle:transition",
            ]
        )
        event_log["repetition"] = event_log.groupby(
            ["case:concept:name", "concept:name", "lifecycle:transition"]
        ).cumcount()
    else:
        event_log.sort_values(["case:concept:name", "time:timestamp", "concept:name"])
        event_log["repetition"] = event_log.groupby(
            ["case:concept:name", "concept:name"]
        ).cumcount()
    event_log["repetition"] = event_log["repetition"] % max_distinction
    event_log["concept:name"] = (
        event_log["concept:name"]
        + "_"
        + event_log["repetition"].astype(str).str.zfill(digits)
    )

    process_tree = discover_process_tree_inductive(
        event_log, noise_threshold=noise_threshold
    )

    # Remove counts from process tree labels
    for leaf in get_leaves(process_tree):
        if leaf.label:
            leaf.label = leaf.label[: -(digits + 1)]

    return process_tree


if __name__ == "__main__":
    from pm4py.objects.process_tree.utils.generic import parse as parse_process_tree

    process_tree = parse_process_tree("->(*(X(->('a', 'b'), +('c', 'd')), tau), 'e')")
    print(find_shortest_replayable_trace_length(process_tree))
