from itertools import product
from typing import List

import networkx as nx
import pandas as pd
from inductive_miner.cuts.base_cut import BaseCut
from inductive_miner.cuts.cut_utils import (
    ENABLE_EXPLICIT_EMPTY_TRACE_CHECK,
    merge_groups,
)
from rules import (
    AbstractRule,
    EndRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    ResponseRule,
)


class SequenceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("SequenceCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    @staticmethod
    def check_rules(rules: List[AbstractRule], groups: List[set]) -> bool:
        unsat_rules = []
        for rule in rules:
            if isinstance(rule, InitializationRule):
                if rule.target_activity not in groups[0]:
                    unsat_rules.append(rule)
            elif isinstance(rule, EndRule):
                if rule.target_activity not in groups[-1]:
                    unsat_rules.append(rule)
            elif isinstance(rule, NotCoExistenceRule):
                group_a_idx = [
                    i for i in range(len(groups)) if rule.activity_a in groups[i]
                ]
                group_a_idx = group_a_idx[0] if group_a_idx else None
                group_b_idx = [
                    i for i in range(len(groups)) if rule.activity_b in groups[i]
                ]
                group_b_idx = group_b_idx[0] if group_b_idx else None
                if (
                    group_a_idx is not None
                    and group_b_idx is not None
                    and group_a_idx != group_b_idx
                ):
                    unsat_rules.append(rule)
            elif isinstance(rule, PrecedenceRule) or isinstance(rule, ResponseRule):
                group_a_idx = [
                    i for i in range(len(groups)) if rule.activity_a in groups[i]
                ]
                group_a_idx = group_a_idx[0] if group_a_idx else None
                group_b_idx = [
                    i for i in range(len(groups)) if rule.activity_b in groups[i]
                ]
                group_b_idx = group_b_idx[0] if group_b_idx else None
                if (
                    group_a_idx is not None
                    and group_b_idx is not None
                    and group_a_idx > group_b_idx
                ):
                    unsat_rules.append(rule)
            elif isinstance(rule, NotSuccessionRule):
                group_a_idx = [
                    i for i in range(len(groups)) if rule.activity_a in groups[i]
                ]
                group_a_idx = group_a_idx[0] if group_a_idx else None
                group_b_idx = [
                    i for i in range(len(groups)) if rule.activity_b in groups[i]
                ]
                group_b_idx = group_b_idx[0] if group_b_idx else None
                if (
                    group_a_idx is not None
                    and group_b_idx is not None
                    and group_a_idx < group_b_idx
                ):
                    unsat_rules.append(rule)
        return unsat_rules

    def __construct_transitive_successors_and_predecessors(
        self, activities: set, dfg: nx.DiGraph
    ) -> dict:
        tc_graph = nx.transitive_closure(dfg)
        successors = {n: set(tc_graph.successors(n)) for n in activities}
        predecessors = {n: set(tc_graph.predecessors(n)) for n in activities}
        return successors, predecessors

    def discover(self) -> List[List[str]]:
        (
            transitive_successors,
            transitive_predecessors,
        ) = self.__construct_transitive_successors_and_predecessors(
            set(self.dfg.nodes), self.dfg
        )
        # Basic steps to perform
        # Create group per activity
        # Merge reachable groups
        # Merge unreachable groups
        # Sort groups based on reachability

        # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: aj ---> ai \not \in the DFG where ----> means eventually follows
        # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: ai ---> aj in the DFG where ----> means eventually follows
        if not ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            if "ArtificialNoneNode" in self.dfg.nodes:
                self.dfg.remove_node("ArtificialNoneNode")

        if "ArtificialNoneNode" in self.dfg.nodes and ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            # We have only empty traces, so we return None to indicate that we cannot apply this cut
            return None
        activities = set(self.dfg.nodes)
        groups = [{activity} for activity in activities]
        if not groups:
            return None
        # Merging groups based on eventually follows relations
        for act1, act2 in product(activities, activities):
            if act1 != act2:
                if (
                    act2 in transitive_successors[act1]
                    and act1 in transitive_successors[act2]
                ):
                    # Reachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
                elif (
                    act2 not in transitive_successors[act1]
                    and act1 not in transitive_successors[act2]
                ):
                    # Unreachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
        # Sorting groups based on reachability
        groups = list(
            sorted(
                groups,
                key=lambda g: len(transitive_predecessors[next(iter(g))])
                + (len(activities) - len(transitive_successors[next(iter(g))])),
            )
        )
        return groups if len(groups) > 1 else None

    def relaxed_projection(
        self, log, groups, activity_key="concept:name", case_key="case:concept:name"
    ):
        sublogs = [[] for _ in groups]

        for trace in log:
            split_point = 0
            act_union = set()

            for idx, group in enumerate(groups):
                new_split_point = self.find_split_point(
                    trace, group, split_point, act_union
                )

                subtrace = []
                j = split_point
                while j < new_split_point:
                    if trace[j] in group:
                        subtrace.append(trace[j])
                    j += 1

                # if group occurs later but current projection is empty, include first occurrence
                if not subtrace:
                    k = split_point
                    while k < len(trace):
                        if trace[k] in group:
                            new_split_point = k + 1
                            subtrace = [trace[k]]
                            break
                        k += 1

                sublogs[idx].append(subtrace)
                split_point = new_split_point
                act_union |= group

        return sublogs

    def project(
        self, log, groups, activity_key="concept:name", case_key="case:concept:name"
    ):
        sublogs = [[] for _ in groups]

        for trace in log:
            split_point = 0
            act_union = set()

            for idx, group in enumerate(groups):
                new_split_point = self.find_split_point(
                    trace, group, split_point, act_union
                )

                subtrace = []
                j = split_point
                while j < new_split_point:
                    if trace[j] in group:
                        subtrace.append(trace[j])
                    j += 1

                sublogs[idx].append(subtrace)
                split_point = new_split_point
                act_union |= group

        return sublogs

    @staticmethod
    def find_split_point(trace, group, start_idx, ignore):
        min_cost = 0
        pos = start_idx
        cost = 0
        idx = start_idx

        while idx < len(trace):
            if trace[idx] in group:
                cost -= 1
            elif trace[idx] not in ignore:
                cost += 1

            if cost < min_cost:
                min_cost = cost
                pos = idx + 1

            idx += 1

        return pos


class BinarySequenceCut(SequenceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinarySequenceCut"

    def discover(self) -> List[List[str]]:
        groups = super().discover()
        merged_rest = set().union(*groups[1:])
        return [groups[0], merged_rest]

    def project(
        self,
        log: List[List[str]],
        groups: List[set],
        activity_key: str = "concept:name",
        case_key: str = "case:concept:name",
    ) -> pd.DataFrame:
        # Just call the super class on that
        return super().project(log, groups, activity_key, case_key)
