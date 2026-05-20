import csv
import random
import timeit
from multiprocessing import cpu_count, Pool, TimeoutError
from pathlib import Path
from typing import TYPE_CHECKING, Union

import gurobipy as gp
from metrics.alignments import add_labels_to_process_tree, dyn_align, ProcessTreeGraph
from metrics.alignments.dynamic_alignment import check_unique_labels
from metrics.alignments.process_tree_alignment import align_multithreaded as align
from metrics.alignments.utils import find_shortest_replayable_trace_length
from pm4py import Marking, PetriNet, ProcessTree
from pm4py.algo.conformance.alignments.petri_net.algorithm import (
    __close_progress_bar as close_progress_bar,
    __get_progress_bar as get_progress_bar,
    __get_variants_structure as get_variants,
    apply as pm4py_align_petri_net,
)
from pm4py.algo.conformance.alignments.process_tree.algorithm import (
    apply as pm4py_align_process_tree,
)
from pm4py.objects.conversion.process_tree.converter import (
    apply as process_tree_to_petri_net,
)
from pm4py.objects.log.obj import EventLog, Trace

if TYPE_CHECKING:
    import pandas as pd


# Set seed for reproducibility
random.seed(42)
# Number of CPUs to use
N_CPUS = cpu_count()
N_WORKERS = min(N_CPUS - 2, 61)
TIMEOUT = 65
MAX_TRACE_VARIANTS = 1000
OFFSET = 0

# Global variable to hold the Gurobi environment in each worker
env = None


def init_worker_env():
    """
    Initialize the Gurobi environment for each worker.
    This function is called once per worker process.
    """
    global env
    # Create a new Gurobi environment
    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 0)  # Suppress Gurobi output
    env.start()


def calculate_log_fitness_pta(
    event_log: Union[EventLog, "pd.DataFrame"],
    process_tree: ProcessTree,
) -> float:
    """
    Calculate log fitness using PTA alignments.

    Works on trace variants for efficiency, but computes log fitness as:

        1 - sum(costs) / sum(denominators)

    where each variant contributes according to its frequency.
    """

    len_shortest_replayable = find_shortest_replayable_trace_length(process_tree)
    ProcessTreeGraph(process_tree)

    variants_struct = get_variants(event_log, None)

    trace_variants: list[tuple[tuple[str, ...], int, Trace]] = [
        (variant, len(instances), trace)
        for (variant, instances), trace in zip(
            variants_struct[0].items(), variants_struct[1]
        )
    ]

    global env
    if env is None:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()

    total_cost = 0.0
    total_denominator = 0.0

    for variant, freq, trace in trace_variants:
        costs, _, _ = evaluate_trace_dyn_align(
            trace=variant,
            process_tree=process_tree,
            len_shortest_replayable_trace=len_shortest_replayable,
            repeat=1,
        )

        cost = costs[0]
        denominator = len(trace) + len_shortest_replayable

        if cost > denominator:
            raise ValueError(
                f"Alignment cost exceeds the maximum expected unit-cost bound: "
                f"cost={cost}, bound={denominator}, "
                f"trace_length={len(trace)}, "
                f"shortest_replayable_trace_length={len_shortest_replayable}, "
                f"trace={trace!r}"
            )

        total_cost += cost * freq
        total_denominator += denominator * freq

    if total_denominator == 0:
        return 0.0

    return 1 - total_cost / total_denominator


def calculate_avg_trace_fitness_pta(
    event_log: Union[EventLog, "pd.DataFrame"],
    process_tree: ProcessTree,
) -> float:
    """
    Calculate average trace fitness for an event log using evaluate_trace_pta.

    This computes fitness for every trace in the event log and returns the
    plain, unweighted average over traces.
    """

    len_shortest_replayable = find_shortest_replayable_trace_length(process_tree)
    process_tree_graph = ProcessTreeGraph(process_tree)
    trace_variants = get_variants(event_log, None)
    trace_variants: list[tuple[tuple[str, ...], int, Trace]] = [
        (k, len(v), t)
        for (k, v), t in zip(trace_variants[0].items(), trace_variants[1])
    ]

    global env
    if env is None:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()

    total_weighted_fitness = 0.0
    total_traces = 0

    for variant, freq, trace in trace_variants:
        _, _, fitness = evaluate_trace_pta(
            trace=trace,
            process_tree_graph=process_tree_graph,
            len_shortest_replayable_trace=len_shortest_replayable,
            repeat=1,
        )

        trace_fitness = fitness[0]
        total_weighted_fitness += trace_fitness * freq
        total_traces += freq

    if total_traces == 0:
        return 0.0

    return total_weighted_fitness / total_traces


def evaluate_trace_dyn_align(
    trace: tuple[str, ...],
    process_tree: ProcessTree,
    len_shortest_replayable_trace: int = -1,
    repeat=10,
) -> tuple[list[float], list[float]]:
    costs = []
    times = timeit.repeat(
        "costs.append(dyn_align(trace, process_tree))",
        repeat=repeat,
        number=1,
        globals={
            "costs": costs,
            "dyn_align": dyn_align,
            "trace": trace,
            "process_tree": process_tree,
        },
    )
    fitness = []

    if len_shortest_replayable_trace >= 0:
        for cost in costs:
            denominator = len(trace) + len_shortest_replayable_trace
            if cost > denominator:
                raise ValueError(
                    f"Alignment cost exceeds the maximum expected unit-cost bound: "
                    f"cost={cost}, bound={denominator}, "
                    f"trace_length={len(trace)}, "
                    f"shortest_replayable_trace_length={len_shortest_replayable_trace}, "
                    f"trace={trace!r}"
                )
            fitness.append(1 - cost / (len(trace) + len_shortest_replayable_trace))

    return costs, times, fitness


def evaluate_trace_pta(
    trace: tuple[str, ...],
    process_tree_graph: ProcessTreeGraph,
    len_shortest_replayable_trace: int = -1,
    repeat=10,
) -> tuple[list[float], list[float]]:
    global env
    costs = []
    times = timeit.repeat(
        "costs.append(align(trace, process_tree_graph, env))",
        repeat=repeat,
        number=1,
        globals={
            "costs": costs,
            "align": align,
            "trace": trace,
            "process_tree_graph": process_tree_graph,
            "env": env,
        },
    )
    fitness = []
    if len_shortest_replayable_trace >= 0:
        for cost in costs:
            denominator = len(trace) + len_shortest_replayable_trace
            if cost > denominator:
                raise ValueError(
                    f"Alignment cost exceeds the maximum expected unit-cost bound: "
                    f"cost={cost}, bound={denominator}, "
                    f"trace_length={len(trace)}, "
                    f"shortest_replayable_trace_length={len_shortest_replayable_trace}, "
                    f"trace={trace!r}"
                )

            fitness.append(1 - cost / (len(trace) + len_shortest_replayable_trace))

    return costs, times, fitness


def evaluate_trace_pm4py_pt(
    trace: Trace,
    process_tree: ProcessTree,
    len_shortest_replayable_trace: int = -1,
    repeat: int = 10,
) -> tuple[list[float], list[float]]:
    costs = []
    times = timeit.repeat(
        'costs.append(pm4py_align_process_tree(trace, process_tree)["cost"])',
        repeat=repeat,
        number=1,
        globals={
            "costs": costs,
            "pm4py_align_process_tree": pm4py_align_process_tree,
            "trace": trace,
            "process_tree": process_tree,
        },
    )
    fitness = []
    if len_shortest_replayable_trace >= 0:
        for cost in costs:
            denominator = len(trace) + len_shortest_replayable_trace
            real_cost = int(cost / 10000)

            if real_cost > denominator:
                raise ValueError(
                    f"Alignment cost exceeds the maximum expected unit-cost bound: "
                    f"cost={cost}, bound={denominator}, "
                    f"trace_length={len(trace)}, "
                    f"shortest_replayable_trace_length={len_shortest_replayable_trace}, "
                    f"trace={trace!r}"
                )
            # pm4py moment
            fitness.append(1 - real_cost / (len(trace) + len_shortest_replayable_trace))

    return costs, times, fitness


def evaluate_trace_pm4py(
    trace: Trace,
    accepting_petri_net: tuple[PetriNet, Marking, Marking],
    len_shortest_replayable_trace: int = -1,
    repeat: int = 10,
) -> tuple[list[float], list[float]]:
    costs = []
    times = timeit.repeat(
        'costs.append(pm4py_align_petri_net(trace, *accepting_petri_net)["cost"])',
        repeat=repeat,
        number=1,
        globals={
            "costs": costs,
            "pm4py_align_petri_net": pm4py_align_petri_net,
            "trace": trace,
            "accepting_petri_net": accepting_petri_net,
        },
    )
    fitness = []
    if len_shortest_replayable_trace >= 0:
        for cost in costs:
            denominator = len(trace) + len_shortest_replayable_trace
            real_cost = int(cost / 10000)
            if real_cost > denominator:
                raise ValueError(
                    f"Alignment cost exceeds the maximum expected unit-cost bound: "
                    f"cost={cost}, bound={denominator}, "
                    f"trace_length={len(trace)}, "
                    f"shortest_replayable_trace_length={len_shortest_replayable_trace}, "
                    f"trace={trace!r}"
                )

            fitness.append(1 - real_cost / (len(trace) + len_shortest_replayable_trace))

    return costs, times, fitness


def evaluate_event_log(
    event_log: Union[EventLog, "pd.DataFrame"],
    process_tree: ProcessTree,
    repeat: int = 5,
    result_path: str | Path = "output",
    file_tag: str = "",
    max_trace_variants: int = MAX_TRACE_VARIANTS,
    include_dyn_align: bool = True,
    include_pt_align: bool = True,
    include_pm4py_align: bool = True,
) -> None:
    if isinstance(result_path, str):
        result_path = Path(result_path)
    if not result_path.is_dir():
        result_path.mkdir(parents=True, exist_ok=True)

    # Get trace variant results and shuffle them
    trace_variants = get_variants(event_log, None)
    trace_variants: list[tuple[tuple[str, ...], int, Trace]] = [
        (k, len(v), t)
        for (k, v), t in zip(trace_variants[0].items(), trace_variants[1])
    ]
    random.shuffle(trace_variants)
    len_shortest_replayable = find_shortest_replayable_trace_length(process_tree)
    # Check if number of trace_variants is below max_trace_variants
    if len(trace_variants) > max_trace_variants:
        trace_variants = trace_variants[OFFSET : (max_trace_variants + OFFSET)]

    # Dynamic Program
    if include_dyn_align:
        print("Align event log using Dynamic Program")
        # Add labels to process tree
        add_labels_to_process_tree(process_tree)
        if check_unique_labels(process_tree):
            with Pool(processes=N_WORKERS) as pool:
                progress_bar = get_progress_bar(len(trace_variants), None)
                results = [
                    (
                        variant,
                        freq,
                        pool.apply_async(
                            evaluate_trace_dyn_align,
                            args=(
                                variant,
                                process_tree,
                                len_shortest_replayable,
                                repeat,
                            ),
                        ),
                    )
                    for variant, freq, trace in trace_variants
                ]
                with open(
                    result_path / f"result{file_tag}_dyn_align.csv", "w", newline=""
                ) as result_file:
                    result_writer = csv.writer(result_file, delimiter="\t")
                    for variant, freq, result in results:
                        try:
                            costs, times, fitness = result.get(timeout=TIMEOUT * repeat)
                            for _ in range(repeat):
                                # Write the results to the CSV file
                                result_writer.writerow(
                                    [
                                        costs.pop(),
                                        times.pop(),
                                        fitness.pop(),
                                        freq,
                                        variant,
                                    ]
                                )
                        except TimeoutError:
                            # print(f"Timeout for trace variant: {variant}")
                            # Write a timeout entry
                            result_writer.writerow(
                                ["timeout", "timeout", freq, variant]
                            )
                        finally:
                            result_file.flush()
                            progress_bar.update()
                close_progress_bar(progress_bar)
        else:
            print(
                "Process tree does not have unique labels, skipping Dynamic Program alignments."
            )

    # Process Tree Alignments
    if include_pt_align:
        print("Align event log using Process Tree Alignments")
        # Build process tree graph
        process_tree_graph = ProcessTreeGraph(process_tree)
        with Pool(processes=N_WORKERS, initializer=init_worker_env) as pool:
            progress_bar = get_progress_bar(len(trace_variants), None)
            results = [
                (
                    variant,
                    freq,
                    pool.apply_async(
                        evaluate_trace_pta,
                        args=(
                            trace,
                            process_tree_graph,
                            len_shortest_replayable,
                            repeat,
                        ),
                    ),
                )
                for variant, freq, trace in trace_variants
            ]
            with open(
                result_path / f"result{file_tag}_pta_align.csv", "w", newline=""
            ) as result_file:
                result_writer = csv.writer(result_file, delimiter="\t")
                for variant, freq, result in results:
                    try:
                        costs, times, fitness = result.get(timeout=TIMEOUT * repeat)
                        for _ in range(repeat):
                            # Write the results to the CSV file
                            result_writer.writerow(
                                [costs.pop(), times.pop(), fitness.pop(), freq, variant]
                            )
                    except TimeoutError:
                        # print(f"Timeout for trace variant: {variant}")
                        # Write a timeout entry
                        result_writer.writerow(["timeout", "timeout", freq, variant])
                    finally:
                        result_file.flush()
                        progress_bar.update()
            close_progress_bar(progress_bar)

    # PM4Py Alignments
    if include_pm4py_align:
        print("Align event log using PM4Py Process Tree Alignments")
        with Pool(processes=N_WORKERS) as pool:
            progress_bar = get_progress_bar(len(trace_variants), None)
            results = [
                (
                    variant,
                    freq,
                    pool.apply_async(
                        evaluate_trace_pm4py_pt,
                        args=(trace, process_tree, len_shortest_replayable, repeat),
                    ),
                )
                for variant, freq, trace in trace_variants
            ]
            with open(
                result_path / f"result{file_tag}_pm4py_pt_align.csv", "w", newline=""
            ) as result_file:
                result_writer = csv.writer(result_file, delimiter="\t")
                for variant, freq, result in results:
                    try:
                        costs, times, fitness = result.get(timeout=TIMEOUT * repeat)
                        for _ in range(repeat):
                            # Write the results to the CSV file
                            result_writer.writerow(
                                [costs.pop(), times.pop(), fitness.pop(), freq, variant]
                            )
                    except TimeoutError:
                        # print(f"Timeout for trace variant: {variant}")
                        # Write a timeout entry
                        result_writer.writerow(["timeout", "timeout", freq, variant])
                    finally:
                        result_file.flush()
                        progress_bar.update()
            close_progress_bar(progress_bar)

        # Build Petri net
        accepting_petri_net = process_tree_to_petri_net(process_tree)
        print("Align event log using PM4Py Petri Net Alignments")
        with Pool(processes=N_WORKERS) as pool:
            progress_bar = get_progress_bar(len(trace_variants), None)
            results = [
                (
                    variant,
                    freq,
                    pool.apply_async(
                        evaluate_trace_pm4py,
                        args=(
                            trace,
                            accepting_petri_net,
                            len_shortest_replayable,
                            repeat,
                        ),
                    ),
                )
                for variant, freq, trace in trace_variants
            ]
            with open(
                result_path / f"result{file_tag}_pm4py_pn_align.csv", "w", newline=""
            ) as result_file:
                result_writer = csv.writer(result_file, delimiter="\t")
                for variant, freq, result in results:
                    try:
                        costs, times, fitness = result.get(timeout=TIMEOUT * repeat)
                        for _ in range(repeat):
                            # Write the results to the CSV file
                            result_writer.writerow(
                                [costs.pop(), times.pop(), fitness.pop(), freq, variant]
                            )
                    except TimeoutError:
                        # print(f"Timeout for trace variant: {variant}")
                        # Write a timeout entry
                        result_writer.writerow(["timeout", "timeout", freq, variant])
                    finally:
                        result_file.flush()
                        progress_bar.update()
            close_progress_bar(progress_bar)

    return
