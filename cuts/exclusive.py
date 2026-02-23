import networkx as nx
from typing import List
import pandas as pd

from cuts.base_cut import BaseCut

class ExclusiveCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ExclusiveCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # To discover partitions of the graph where no direct follows relations exist between partitions
        # For all i != j and aj \in partition j, ai \in partition i, there is no edge ai -> aj in the DFG
        partitions = nx.weakly_connected_components(self.dfg)
        exclusive_partitions = [set(partition) for partition in partitions]
        return exclusive_partitions
    def project(self, traces : pd.DataFrame, groups: List[set]) -> pd.DataFrame:
        # Projecting the traces onto the given group of activities
        sublogs = []
        for group in groups:
            sublog = traces.copy()
            sublog['trace'] = sublog['trace'].apply(lambda trace: [act for act in trace if act in group])
            sublogs.append(sublog)
        return sublogs
    
    def project_argmax(self, traces: List[str], groups: List[set]) -> dict:
        # Argmax definition of projection according to 
        # Using translucent activity relationships frequencies to enhance process discovery
        # Beyel, van der Aalst (doi: 10.1007/s44311-025-00010-y)
        sublogs : dict = {}
        for trace in traces:
            max_group_projection = []
            max_group_id = None
            for idx, group in enumerate(groups):
                projected_trace = [act for act in trace if act in group]
                if len(projected_trace) > len(max_group_projection):
                    max_group_projection = projected_trace
                    max_group_id = idx
            if max_group_id is not None:
                if max_group_id not in sublogs:
                    sublogs[max_group_id] = []
                sublogs[max_group_id].append(max_group_projection)
        return sublogs

            
            
class BinaryExclusiveCut(ExclusiveCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryExclusiveCut"

    def discover(self) -> List[set]:
        # Ensure that the discovered partitions are exactly two
        partitions = super().discover()
        # Get the biggest partition and merge the rest into one
        if len(partitions) > 2 :
            partitions = sorted(partitions, key=len, reverse=True)
            merged_partition = set()
            for partition in partitions[1:]:
                merged_partition.update(partition)
            partitions = [partitions[0], merged_partition]
        return partitions
    
    def project(self, traces : pd.DataFrame, groups: List[set]) -> pd.DataFrame:
        # Just call the super class on that
        return super().project(traces, groups)
    def project_argmax(self, traces: List[str], groups: List[set]) -> dict:
        return super().project_argmax(traces, groups)