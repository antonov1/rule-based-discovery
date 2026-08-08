from typing import List, Set

import networkx as nx
import pandas as pd
from inductive_miner.cuts.base_cut import BaseCut
from inductive_miner.cuts.cut_utils import ENABLE_EXPLICIT_EMPTY_TRACE_CHECK
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)


class ExclusiveChoiceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ExclusiveChoiceCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    @staticmethod
    def check_rules(rules: List[AbstractRule], groups: List[set]) -> Set[AbstractRule]:
        unsat_rules = []
        for rule in rules:
            if isinstance(rule, (InitializationRule, ExistenceRule, EndRule)):
                unsat_rules.append(rule)
            elif (
                isinstance(rule, PrecedenceRule)
                or isinstance(rule, ChainPrecedenceRule)
                or isinstance(rule, CoExistenceRule)
                or isinstance(rule, ResponseRule)
                or isinstance(rule, ChainResponseRule)
                or isinstance(rule, RespondedExistenceRule)
            ):
                group_a = next(
                    (group for group in groups if rule.activity_a in group), None
                )
                group_b = next(
                    (group for group in groups if rule.activity_b in group), None
                )
                if group_a is not None and group_b is not None and group_a != group_b:
                    unsat_rules.append(rule)
        return set(unsat_rules)

    def discover(self) -> List[set]:
        # To discover partitions of the graph where no direct follows relations exist between partitions
        # For all i != j and aj \in partition j, ai \in partition i, there is no edge ai -> aj in the DFG
        # Enforce that we deal with empty traces as soon as possible:
        if not ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            if "ArtificialNoneNode" in self.dfg.nodes:
                self.dfg.remove_node("ArtificialNoneNode")
        if "ArtificialNoneNode" in self.dfg.nodes and ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            return None
        partitions = nx.weakly_connected_components(self.dfg)
        exclusive_partitions = [set(partition) for partition in partitions]
        # sort them based on the number of nodes and lexicographically to ensure deterministic output
        exclusive_partitions.sort(
            key=lambda x: (-len(x), " ".join(sorted(x))), reverse=False
        )
        return exclusive_partitions if len(exclusive_partitions) > 1 else None

    def project(
        self,
        log: List[List[str]],
        groups: List[set],
        case_key: str = "case:concept:name",
        activity_key: str = "concept:name",
    ) -> pd.DataFrame:
        sublogs = [[] for _ in groups]
        group_mapping = {
            activity: idx for idx, group in enumerate(groups) for activity in group
        }
        # ARGMAX-like projection
        for trace in log:
            count_group = {idx: 0 for idx in range(len(groups))}
            for act in trace:
                if act in group_mapping:
                    count_group[group_mapping[act]] += 1

            ranked = sorted(
                count_group.items(), key=lambda x: (x[1], x[0]), reverse=True
            )
            chosen_group = ranked[0][0]

            projected_trace = [act for act in trace if act in groups[chosen_group]]
            sublogs[chosen_group].append(projected_trace)

        return sublogs


class BinaryExclusiveChoiceCut(ExclusiveChoiceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryExclusiveChoiceCut"

    def discover(self) -> List[set]:
        # Ensure that the discovered partitions are exactly two
        partitions = super().discover()
        # Get the biggest partition and merge the rest into one
        if partitions is not None and len(partitions) > 2:
            partitions = sorted(partitions, key=len, reverse=True)
            merged_partition = set()
            for partition in partitions[1:]:
                merged_partition.update(partition)
            partitions = [partitions[0], merged_partition]
            # If ArtificialNoneNode is in one of the partitions, we need to make sure that everything else
            # Apart from ArtificialNoneNode is in the other partition

        return partitions

    def project(
        self,
        log: List[List[str]],
        groups: List[set],
        case_key: str = "case:concept:name",
        activity_key: str = "concept:name",
    ) -> dict:
        return super().project(log, groups, case_key, activity_key)
