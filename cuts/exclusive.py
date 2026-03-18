import copy
from typing import List

import networkx as nx
import pandas as pd
from cuts.base_cut import BaseCut


class ExclusiveChoiceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ExclusiveChoiceCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # To discover partitions of the graph where no direct follows relations exist between partitions
        # For all i != j and aj \in partition j, ai \in partition i, there is no edge ai -> aj in the DFG
        # Enforce that we deal with empty traces as soon as possible:
        if "ArtificialNoneNode" in self.dfg.nodes:
            return None
        partitions = nx.weakly_connected_components(self.dfg)
        exclusive_partitions = [set(partition) for partition in partitions]
        # sort them based on the number of nodes and lexicographically to ensure deterministic output
        exclusive_partitions.sort(
            key=lambda x: (len(x), " ".join(sorted(x))), reverse=True
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
            partitions_copy = copy.copy(partitions)
            if (
                "ArtificialNoneNode" in partitions_copy[0]
                or "ArtificialNoneNode" in partitions_copy[1]
            ):
                everything_else = set(self.dfg.nodes) - {"ArtificialNoneNode"}
                partitions[1] = {"ArtificialNoneNode"}
                partitions[0] = everything_else

        return partitions

    def project(
        self,
        log: List[List[str]],
        groups: List[set],
        case_key: str = "case:concept:name",
        activity_key: str = "concept:name",
    ) -> dict:
        return super().project(log, groups, case_key, activity_key)
