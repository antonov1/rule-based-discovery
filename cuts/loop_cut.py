from copy import copy
from tracemalloc import start

import networkx as nx
from typing import List
import pandas as pd

from cuts.base_cut import BaseCut

class LoopCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("LoopCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        # Empty DFG means no activities
        if self.dfg is None or len(self.dfg.nodes) == 0:
            return None
        
        # Partition_1 includes the start and end activities
        # i.e., nodes with in-degree 0 or out-degree 0
        start_activities = set(n for n in self.dfg.nodes if self.dfg.nodes[n].get('start', 0) > 0)
        end_activities = set(n for n in self.dfg.nodes if self.dfg.nodes[n].get('end', 0) > 0)
        do = start_activities.union(end_activities)
        if len(do) == 0:
            raise ValueError("No start or end activities found in the DFG, cannot apply LoopCut.")
        activities = set(self.dfg.nodes)
        # The do group is always first
        groups = [do] + self.__reduce_dfg(do, activities)
        real_start_activities = start_activities.difference(end_activities)
        groups = self.__exclude_groups_not_reachable_from_start(self.dfg, groups, real_start_activities)
        real_end_activities = end_activities.difference(start_activities)
        groups = self.__exclude_groups_not_reachable_from_end(self.dfg, groups, real_end_activities)
        groups = self.merge_groups_with_start_activities(self.dfg, groups, start_activities)
        groups = self.merge_groups_with_end_activities(self.dfg, groups, end_activities)
        # sort everything from group[1:] based on the number of nodes and lexicographically to ensure deterministic output
        groups[1:] = sorted(groups[1:], key=lambda x: (len(x), ' '.join(sorted(x))), reverse=True)
        return groups if len(groups) > 1 else None



    def __reduce_dfg(self, do_partition : set, activities : set) -> List[set]:
        new_dfg = self.dfg.copy()
        for (e,v) in self.dfg.edges:
            # We get rid of all edges that are directly connected to the do_partition
            if e in do_partition or v in do_partition:
                new_dfg.remove_edge(e,v)
        resulting_activities = set(activities).difference(do_partition)
        # keep the dfg only with the resulting activities
        new_dfg = new_dfg.subgraph(resulting_activities)
        weakly_connected_components = nx.weakly_connected_components(new_dfg)
        groups = [set(component) for component in weakly_connected_components]
        return groups

    @staticmethod
    def __exclude_groups_not_reachable_from_start(dfg: nx.DiGraph, groups: List[set], start_activities: set) -> List[set]:
        for act in start_activities:
           for (e, v) in dfg.edges:
               if e == act:
                group_v = next((group for group in groups if v in group), None)
                group_a = next((group for group in groups if act in group), None)
                groups = [group for group in groups if group != group_v and group != group_a]
                groups.insert(0, group_v.union(group_a))
        return groups
    @staticmethod
    def __exclude_groups_not_reachable_from_end(dfg: nx.DiGraph, groups: List[set], end_activities: set) -> List[set]:
        for act in end_activities:
           for (e, v) in dfg.edges:
               if v == act:
                group_e = next((group for group in groups if e in group), None)
                group_a = next((group for group in groups if act in group), None)
                groups = [group for group in groups if group != group_e and group != group_a]
                groups.insert(0, group_e.union(group_a))
        return groups
    
    @staticmethod
    def merge_groups_with_start_activities(dfg: nx.DiGraph, groups: List[set], start_activities: set) -> List[set]:
        # Used to satisfy the criterion that all redo-groups should be directly reachable from the start activities
        merged_groups = [groups[0].copy()]
        dfg_edges = [(e,v) for (e,v) in dfg.edges]
        for group in groups[1:]:
            curr_group = group.copy()
            should_merge = any(
                        (node, start) not in dfg_edges for node in group for start in start_activities
                    )

            if should_merge:
                merged_groups[0].update(curr_group)
            else:
                merged_groups.append(curr_group)
        return merged_groups
    
    @staticmethod
    def merge_groups_with_end_activities(dfg: nx.DiGraph, groups: List[set], end_activities: set) -> List[set]:
        # Used to satisfy the criterion that all redo-groups should be directly connected to the end activities
        dfg_edges = [(e,v) for (e,v) in dfg.edges]
        merged_groups = [groups[0].copy()]
        for group in groups[1:]:
            curr_group = group.copy()
            should_merge = any(
                        (end, node) not in dfg_edges for node in group for end in end_activities
                    )

            if should_merge:
                merged_groups[0].update(curr_group)
            else:
                merged_groups.append(curr_group)
        return merged_groups

                

    @staticmethod
    def project(log : pd.DataFrame, groups: List[set], activity_key : str = 'concept:name',
                case_key : str = 'case:concept:name') -> pd.DataFrame:
        sublogs = [[] for _ in groups]
        activity_to_group = {activity: idx for idx, group in enumerate(groups) for activity in group}
        log['group'] = log[activity_key].apply(lambda act: activity_to_group.get(act, None))
        if log['group'].isnull().any():
            raise ValueError("Some activities in the log do not belong to any group, cannot project.")
        # Now divide the log into sublogs based on the group column
        traces = log.groupby(case_key)
        for _, trace in traces:
            prev_group = None
            curr_trace = []
            for idx, event in trace.iterrows():
                if event['group'] is not None and event['group'] != prev_group:
                    if curr_trace and prev_group is not None:
                        sublogs[prev_group].append(trace.loc[curr_trace])
                    curr_trace = [idx]
                    prev_group = event['group']
                else:
                    curr_trace.append(idx)
        sublogs = [pd.concat(sublog) if sublog else pd.DataFrame(columns=log.columns) for sublog in sublogs]
        return sublogs
    
class BinaryLoopCut(LoopCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryLoopCut"

    def discover(self) -> List[set]:
        # Just call the super class on that
        groups = super().discover()
        # Split them in a way s.t. the biggest group is one and the rest of the groups are merged into another
        if groups and len(groups) > 2 :
            merged_group = set()
            for group in groups[1:]:
                merged_group.update(group)
            groups = [groups[0], merged_group]
        return groups
    
    def project(self, log : pd.DataFrame, groups: List[set], activity_key : str = 'concept:name',
                case_key : str = 'case:concept:name') -> pd.DataFrame:
        # Just call the super class on that
        return super().project(log, groups, activity_key=activity_key, case_key=case_key)

if __name__ == "__main__":
    # try with <a>, <a,a,a>, <a,a,a,a,a>
    dfg = nx.DiGraph()
    dfg.add_edge('a', 'a', weight=4)
    dfg.nodes['a']['start'] = 5
    dfg.nodes['a']['end'] = 5
    loop_cut = LoopCut(dfg)
    groups = loop_cut.discover()
    print(groups)

