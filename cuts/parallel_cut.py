import networkx as nx
from typing import List

from numpy import inf
from sympy import Basic
import pandas as pd
from cuts.base_cut import BaseCut
from itertools import product
from cuts.utils import merge_groups
class ParallelCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ParallelCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # The workflow looks like this
        # 0. Create a set/group for each activity
        # 1. Merge not-fully connected sets
        # 2. Merge sets without start/end activities
        groups = [set(activity) for activity in self.dfg.nodes]
        for act1, act2 in product(self.dfg.nodes, self.dfg.nodes):
            if (act1, act2) not in self.dfg.edges and (act2, act1) not in self.dfg.edges:
                groups = merge_groups(groups, act1, act2)
        # Merging sets without start/end activities
        start_activities = {n for n in self.dfg.nodes if self.dfg.in_degree(n) == 0}
        end_activities = {n for n in self.dfg.nodes if self.dfg.out_degree(n) == 0}
        groups = list(sorted(groups, key = lambda g : len(g)))
        while i < len(groups):
            if len(groups) <= 1:
                # We have merged everything into one group, so we can stop
                break
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
        return groups
    def project(self, event_log : pd.DataFrame, groups: List[set], activity_key : str) -> pd.DataFrame:
        # find in which group trace the attribute 'activity_key' is

        event_log['group'] = event_log[activity_key].apply(lambda act: next((idx for idx, group in enumerate(groups) if act in group), None))
        # Split the event log based on the group column
        sublogs = []
        for group_id in event_log['group'].unique():
            sublog = event_log[event_log['group'] == group_id].copy()
            sublog.drop(columns=['group'], inplace=True)
            sublogs.append(sublog)
        return sublogs
    
class BinaryParallelCut(ParallelCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryParallelCut"

    def discover(self) -> List[set]:
        # Just call the super class on that
        groups =  super().discover()
        # Split them in a way s.t. the biggest group is one and the rest of the groups are merged into another
        if len(groups) > 2 :
            groups = sorted(groups, key=len, reverse=True)
            merged_group = set()
            for group in groups[1:]:
                merged_group.update(group)
            groups = [groups[0], merged_group]
        return groups
    def project(self, traces : pd.DataFrame, groups: List[set], activity_key : str) -> pd.DataFrame:
        # Just call the super class on that
        return super().project(traces, groups, activity_key=activity_key)

        
