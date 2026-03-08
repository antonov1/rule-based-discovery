import networkx as nx
from typing import List
import pandas as pd

from cuts.base_cut import BaseCut

class ExclusiveChoiceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ExclusiveChoiceCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # To discover partitions of the graph where no direct follows relations exist between partitions
        # For all i != j and aj \in partition j, ai \in partition i, there is no edge ai -> aj in the DFG
        partitions = nx.weakly_connected_components(self.dfg)
        exclusive_partitions = [set(partition) for partition in partitions]
        # sort them based on the number of nodes and lexicographically to ensure deterministic output
        exclusive_partitions.sort(key=lambda x: (len(x), ' '.join(sorted(x))), reverse=True)
        return exclusive_partitions
    

    def project_standard(self, log : pd.DataFrame, groups: List[set], case_key : str = 'case:concept:name', activity_key : str = 'concept:name') -> pd.DataFrame:
        # Projecting the traces onto the given group of activities
        sublogs = [[] for _ in groups]
        group_mapping = {activity: idx for idx, group in enumerate(groups) for activity in group}
        log['group'] = log[activity_key].apply(lambda act: group_mapping.get(act, None))
        traces = log.groupby(case_key)
        for _, trace in traces:
            for group in trace['group'].unique():
                if group is not None:
                    sublogs[group].append(trace[trace['group'] == group])
        # make sure that each sublog is a single dataframe
        sublogs = [pd.concat(sublog) if sublog else pd.DataFrame(columns=log.columns) for sublog in sublogs]
        return sublogs
        

    
    def project(self, log: pd.DataFrame, groups: List[set], case_key: str = 'case:concept:name', activity_key: str = 'concept:name') -> dict:
        # Argmax definition of projection according to 
        # Using translucent activity relationships frequencies to enhance process discovery
        # Beyel, van der Aalst (doi: 10.1007/s44311-025-00010-y)
        sublogs = [[] for _ in groups]
        group_mapping = {activity: idx for idx, group in enumerate(groups) for activity in group}
        log['group'] = log[activity_key].apply(lambda act: group_mapping.get(act, None))
        traces = log.groupby(case_key)
        for _, trace in traces:
            max_group = trace['group'].value_counts().idxmax()
            if max_group is not None:
                sublogs[max_group].append(trace)
        return [pd.concat(sublog) if sublog else pd.DataFrame(columns=log.columns) for sublog in sublogs]

            
            
class BinaryExclusiveChoiceCut(ExclusiveChoiceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryExclusiveChoiceCut"

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
    
    def project(self, log: pd.DataFrame, groups: List[set], case_key: str = 'case:concept:name', activity_key: str = 'concept:name') -> dict:
        return super().project(log, groups, case_key, activity_key)