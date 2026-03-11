import networkx as nx
from typing import List

from numpy import inf
import pandas as pd
from cuts.base_cut import BaseCut
from itertools import product
from cuts.cut_utils import merge_groups

class SequenceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("SequenceCut", list(dfg.nodes), dfg)
        self.dfg = dfg


        
    def __construct_transitive_successors_and_predecessors(self, activities: set, dfg: nx.DiGraph) -> dict:
        tc_graph = nx.transitive_closure(dfg)
        successors = {n: set(tc_graph.successors(n)) for n in activities}
        predecessors = {n: set(tc_graph.predecessors(n)) for n in activities}
        return successors, predecessors
    

    def discover(self) -> List[List[str]]:
        transitive_successors, transitive_predecessors = self.__construct_transitive_successors_and_predecessors(set(self.dfg.nodes), self.dfg)
        # Basic steps to perform
        # Create group per activity
        # Merge reachable groups
        # Merge unreachable groups
        # Sort groups based on reachability

        # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: aj ---> ai \not \in the DFG where ----> means eventually follows
         # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: ai ---> aj in the DFG where ----> means eventually follows
        activities = set(self.dfg.nodes)
        groups = [{activity} for activity in activities]
        if not groups:
            return None
        # Merging groups based on eventually follows relations
        for act1, act2 in product(activities, activities):
            if act1 != act2:
                if act2 in transitive_successors[act1] and act1 in transitive_successors[act2]:
                    # Reachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
                elif act2 not in transitive_successors[act1] and act1 not in transitive_successors[act2]:
                    # Unreachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
        # Sorting groups based on reachability
        groups = list(sorted(groups, key=lambda g: len(
            transitive_predecessors[next(iter(g))]) + (len(activities) - len(transitive_successors[next(iter(g))]))))
        return groups if len(groups) > 1 else None
    
    def project(self, log : pd.DataFrame, groups: List[set], activity_key = 'concept:name', case_key = 'case:concept:name') -> pd.DataFrame:
        # Projecting the traces onto the given group of activities
        # Groups are ordered based on transitivity so we can always start iterating from beginning
        sublogs = [[] for _ in groups]
        traces = log.groupby(case_key)
        for _, trace in traces:
            split_point = 0
            act_union = set()
            trace_as_list = trace[activity_key].tolist()
            for idx, group in enumerate(groups):
                split = self.find_split_point(trace_as_list, split_point, group)
                j = split_point
                subtrace = []
                while j <= split and j < len(trace_as_list):
                    if trace_as_list[j] in group:
                        # append the j-th event from trace to the subtrace
                        subtrace.append(trace.index[j])
                    j += 1
                if subtrace:
                    projected = trace.loc[subtrace].copy()
                else:
                    projected = pd.DataFrame([{col: None for col in log.columns}])
                    projected[case_key] = trace[case_key].iloc[0]
                sublogs[idx].append(projected)
                split_point = split
                act_union = act_union.union(set(group))

        return [
            pd.concat(sublog, ignore_index=True) if sublog
            else pd.DataFrame(columns=log.columns)
            for sublog in sublogs
        ]    
    @staticmethod
    def find_split_point(trace, start_idx : int, group : set) -> int:
        "Tries to identify minimal split point wrt cost"
        min_cost = inf
        pos = start_idx
        cost = 0
        idx = start_idx
        while idx < len(trace):
            if trace[idx] in group:
                cost -= 1
            else:
                cost += 1
            if cost < min_cost:
                min_cost = cost
                pos = idx
            idx += 1
        return pos

class BinarySequenceCut(SequenceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinarySequenceCut"

    def discover(self) -> List[List[str]]:
        groups = super().discover()
        if groups and len(groups) > 2:
            # Split them in the middle
            mid = len(groups) // 2
            return [set().union(*groups[:mid]), set().union(*groups[mid:])]
        return groups
    
    def project(self, traces : pd.DataFrame, groups: List[set], activity_key: str = 'concept:name', case_key: str = 'case:concept:name') -> pd.DataFrame:
        # Just call the super class on that
        return super().project(traces, groups, activity_key, case_key)
    