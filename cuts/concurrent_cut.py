import networkx as nx   
from typing import List

from networkx.utils import groups
import pandas as pd
from cuts.base_cut import BaseCut
from itertools import product
from cuts.cut_utils import merge_groups

class ConcurrentCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ConcurrentCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # The workflow looks like this
        # 0. Create a set/group for each activity
        # 1. Merge not-fully connected sets
        # 2. Merge sets without start/end activities
        if 'ArtificialNoneNode' in self.dfg.nodes:
            # To make sure that empty traces are 
            # always handled first
            return None
        groups = [{a} for a in self.dfg.nodes]
        for act1, act2 in product(self.dfg.nodes, self.dfg.nodes):
            if (act1, act2) not in self.dfg.edges or (act2, act1) not in self.dfg.edges:
                groups = merge_groups(groups, act1, act2)
        # Merging sets without start/end activities
        # nodes with attribute start > 0
        start_activities = set(n for n in self.dfg.nodes if self.dfg.nodes[n].get('start', 0) > 0)
        end_activities = set(n for n in self.dfg.nodes if self.dfg.nodes[n].get('end', 0) > 0)
        groups = list(sorted(groups, key = lambda g : len(g)))
        i = 0
        while i < len(groups) and len(groups) > 1:
            # if len(groups) == 1: we merged everything together
            group = groups[i]
            if group.intersection(start_activities) and group.intersection(end_activities):
                # This group has both start and end activities, so we can skip it
                i += 1
                continue
            # This group does not have both start and end activities, so we need to merge it
            current_group = groups.pop(i)
            if i == 0:
                # We are at the beginning, so we can only merge with the next group
                groups[0] = groups[0].union(current_group)
            else:
                # add to previous group
                groups[i-1] = groups[i-1].union(current_group)
        groups = list(sorted(groups, key=lambda x: (len(x), ' '.join(sorted(x))), reverse=True))
        return groups if len(groups) > 1 else None
    
    @staticmethod
    def project(event_log : List[List[str]], groups: List[set], activity_key : str = 'concept:name', case_key : str = 'case:concept:name') -> pd.DataFrame:
        # find in which group trace the attribute 'activity_key' is
        sublogs = [[] for _ in range(len(groups))]
        for trace in event_log:
            for idx, group in enumerate(groups):
                projected_trace = [act for act in trace if act in group]
                if projected_trace:
                    sublogs[idx].append(projected_trace)
        return sublogs

    
class BinaryConcurrentCut(ConcurrentCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryConcurrentCut"

    def discover(self) -> List[set]:
        # Just call the super class on that
        groups =  super().discover()
        # Split them in a way s.t. the biggest group is one and the rest of the groups are merged into another
        if groups is not None and len(groups) > 2 :
            # create a string out of each group based on the sorted activities in the group and sort them based on length
            merged_group = set()
            for group in groups[1:]:
                merged_group.update(group)
            groups = [groups[0], merged_group]
        return groups
    
    def project(self, log : List[List[str]], groups: List[set], activity_key : str = 'concept:name', case_key : str = 'case:concept:name') -> pd.DataFrame:
        # Just call the super class on that
        return super().project(log, groups, activity_key=activity_key, case_key=case_key)

