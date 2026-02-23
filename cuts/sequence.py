import networkx as nx
from typing import List

from numpy import inf
from sympy import Basic
import pandas as pd
from cuts.base_cut import BaseCut
from itertools import product
from cuts.utils import merge_groups

class SequenceCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("SequenceCut", list(dfg.nodes), dfg)
        self.dfg = dfg


        
    def __construct_transitive_successors_and_predecessors(self, activities: set, dfg: nx.DiGraph) -> dict:
        tc_graph = nx.transitive_closure(dfg)
        successors = {n: set(tc_graph.successors(n)) for n in activities}
        predecessors = {n: set(tc_graph.predecessors(n)) for n in activities}
        return successors, predecessors
    

    def discover(self, transitive_successors, transitive_predecessors) -> List[List[str]]:
        # Basic steps to perform
        # Create group per activity
        # Merge reachable groups
        # Merge unreachable groups
        # Sort groups based on reachability

        # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: aj ---> ai \not \in the DFG where ----> means eventually follows
         # For all 1 <= i < j <= n ai \in Sigma_i and aj \in Sigma j: ai ---> aj in the DFG where ----> means eventually follows
        activities = set(self.dfg.nodes)
        groups = [set(activity) for activity in activities if self.dfg.in_degree(activity) == 0]
        if not groups:
            return None
        # Merging groups based on eventually follows relations
        for act1, act2 in product(activities, activities):
            if act1 != act2:
                if act2 in transitive_successors[act1] and act1 in transitive_predecessors[act2]:
                    # Reachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
                elif act2 not in transitive_successors[act1] and act1 not in transitive_predecessors[act2]:
                    # Unreachable groups should be merged together
                    groups = merge_groups(groups, act1, act2)
        # Sorting groups based on reachability
        groups = list(sorted(groups, key=lambda g: len(
            transitive_predecessors[next(iter(g))]) + (len(activities) - len(transitive_successors[next(iter(g))]))))
        return groups if len(groups) > 1 else None
    def project(self, traces : pd.DataFrame, groups: List[set]) -> pd.DataFrame:
        # Projecting the traces onto the given group of activities
        # Groups are ordered based on transitivity so we can always start iterating from beginning
        sublogs = dict()
        for trace in traces:
            i, split_point = 0, 0
            subtrace = []
            act_union = set()

            for idx, group in enumerate(groups):
                split = self.find_split_point(trace, split_point, group)
                j = split_point
                while j < split:
                    if trace[j] in group:
                        subtrace.append(trace[j])
                        act_union.add(trace[j])
                    j += 1
                if idx not in sublogs:
                    sublogs[idx] = []
                sublogs[idx].append(subtrace)
                split_point = split
                act_union = act_union.union(set(group))
                i+=1
        return sublogs
    
    @staticmethod
    def find_split_point(trace, start_idx : int, group : set) -> int:
        "Tries to identify minimal split point wrt cost"
        from numpy import inf
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

    def discover(self, transitive_successors, transitive_predecessors) -> List[List[str]]:
        groups = super().discover(transitive_successors, transitive_predecessors)
        if groups and len(groups) > 2:
            # Split them in the middle
            mid = len(groups) // 2
            return [set().union(*groups[:mid]), set().union(*groups[mid:])]
        return groups
    
    def project(self, traces : pd.DataFrame, groups: List[set]) -> pd.DataFrame:
        # Just call the super class on that
        return super().project(traces, groups)