from typing import List, Tuple

import networkx as nx
from cuts import (
    BinaryConcurrentCut,
    BinaryExclusiveChoiceCut,
    BinaryLoopCut,
    BinarySequenceCut,
    ConcurrentCut,
    ExclusiveChoiceCut,
    LoopCut,
    SequenceCut,
)
from pm4py.objects.process_tree.obj import Operator
from utils.directly_follows_graph import DirectlyFollowsGraph


def empty_traces(log: List[List[str]], **kwargs) -> Tuple[List[List[str]], Operator]:
    # Base case for when we have empty traces in the log
    if [] in log:
        log_without_empty = [trace for trace in log if trace]
        return [log_without_empty, []], Operator.XOR
    return None


def activity_once_per_trace(
    log: List[List[str]], **kwargs
) -> Tuple[List[List[str]], Operator]:
    # Base case for when all activities occur at most once per trace
    # Find candidate activities (should appear exactly once in EVERY trace)
    candidate_activities = set(log[0])  # Start with activities from the first trace
    activities = set([activity for trace in log for activity in trace])
    for trace in log:
        for activity in candidate_activities.copy():
            if trace.count(activity) != 1:
                candidate_activities.remove(activity)
    if len(candidate_activities):
        candidate_activities = list(candidate_activities)
        # sort them based on lexicographical order to ensure deterministic output
        candidate_activities.sort()
    else:
        return None

    # If we are in binary mode, we can only return a single activity as a leaf node
    candidate = candidate_activities[0]

    if candidate_activities:
        binary_cut = BinaryConcurrentCut(nx.DiGraph())

        groups = [{candidate}, set(activities).difference({candidate})]
        projections = binary_cut.project(log, groups)
        return projections, Operator.PARALLEL

    return None


def activity_concurrent(
    log: List[List[str]], binary: bool = False, **kwargs
) -> Tuple[List[List[str]], Operator]:
    # Base case for when an activity occurs at least once in every trace and the activity is concurrent with all other activities
    activities = set([activity for trace in log for activity in trace])
    candidates = activities.copy()
    for trace in log:
        for activity in candidates.copy():
            if trace.count(activity) == 0:
                candidates.remove(activity)
    if not candidates:
        return None
    candidates = sorted(list(candidates))
    cuts_order = (
        [
            BinaryExclusiveChoiceCut,
            BinarySequenceCut,
            BinaryConcurrentCut,
            BinaryLoopCut,
        ]
        if binary
        else [ExclusiveChoiceCut, SequenceCut, ConcurrentCut, LoopCut]
    )
    for candidate in candidates:
        projections = BinaryConcurrentCut(nx.DiGraph()).project(
            log, [{candidate}, set(activities).difference({candidate})]
        )
        sublog_1 = projections[1]
        # Try to identify a cut
        new_dfg = DirectlyFollowsGraph(sublog_1).graph
        for cut in cuts_order:
            cut_instance = cut(new_dfg)
            groups = cut_instance.discover()
            if groups:
                return projections, Operator.PARALLEL
    return None


def strict_tau_loop(
    log: List[List[str]], end_activities: set, start_activities: set, **kwargs
) -> Tuple[List[List[str]], Operator]:
    # Split trace whenever end activity is followed by start activity
    new_log = []
    for trace in log:
        subtrace = [trace[0]] if trace else []

        for curr, nxt in zip(trace, trace[1:]):
            if curr in end_activities and nxt in start_activities:
                new_log.append(subtrace)
                subtrace = [nxt]
            else:
                subtrace.append(nxt)

        if subtrace:
            new_log.append(subtrace)

    if len(new_log) > len(log):
        return [new_log, []], Operator.LOOP
    return None


def tau_loop(
    log: List[List[str]], start_activities: set, **kwargs
) -> Tuple[List[List[str]], Operator]:
    # Split trace whenever end activity is followed by start activity, but also allow for traces that do not follow this pattern
    new_log = []
    for trace in log:
        subtrace = [trace[0]] if trace else []
        for curr, nxt in zip(trace, trace[1:]):
            if nxt in start_activities:
                new_log.append(subtrace)
                subtrace = [nxt]
            else:
                subtrace.append(nxt)
        if subtrace:
            new_log.append(subtrace)
    if len(new_log) > len(log):
        return [new_log, []], Operator.LOOP
    return None
