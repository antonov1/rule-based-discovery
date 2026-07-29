from typing import List

import networkx as nx
import pandas as pd
from inductive_miner.cuts.base_cut import BaseCut
from inductive_miner.cuts.cut_utils import ENABLE_EXPLICIT_EMPTY_TRACE_CHECK
from rules import (
    AbstractRule,
    AtMostOnceRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)


class LoopCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("LoopCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    @staticmethod
    def check_rules(rules: List[AbstractRule], groups: List[set]) -> bool:
        unsat_rules = []
        _, group_rest = groups[0], groups[1:]
        for rule in rules:
            if isinstance(rule, ExistenceRule):
                if any(rule.target_activity in group for group in group_rest):
                    unsat_rules.append(rule)
            elif isinstance(rule, InitializationRule) or isinstance(rule, EndRule):
                if any(rule.target_activity in group for group in group_rest):
                    unsat_rules.append(rule)
            elif isinstance(rule, AtMostOnceRule):
                if any(rule.target_activity in group for group in groups):
                    unsat_rules.append(rule)
            elif (
                isinstance(rule, CoExistenceRule)
                or isinstance(rule, ResponseRule)
                or isinstance(rule, ChainResponseRule)
            ):
                # In response, we have <x,y,x> obvious violation so they should appear together in the same group
                group_a = next(
                    (group for group in groups if rule.activity_a in group), None
                )
                group_b = next(
                    (group for group in groups if rule.activity_b in group), None
                )
                if group_a is not None and group_b is not None and group_a != group_b:
                    unsat_rules.append(rule)
            elif isinstance(rule, PrecedenceRule) or isinstance(
                rule, ChainPrecedenceRule
            ):
                # We have to check if b is in the do part and a is in the redo part
                if rule.activity_b in groups[0] and any(
                    rule.activity_a in group for group in group_rest
                ):
                    unsat_rules.append(rule)
            elif isinstance(rule, RespondedExistenceRule):
                # We have to check if b is in the do part and a is in the redo part
                if rule.activity_a in groups[0] and any(
                    rule.activity_b in group for group in group_rest
                ):
                    unsat_rules.append(rule)
            elif isinstance(rule, NotSuccessionRule):
                a_present = any(rule.activity_a in group for group in groups)
                b_present = any(rule.activity_b in group for group in groups)
                if a_present and b_present:
                    unsat_rules.append(rule)
            elif isinstance(rule, NotCoExistenceRule):
                if any(rule.activity_a in group for group in groups) and any(
                    rule.activity_b in group for group in groups
                ):
                    unsat_rules.append(rule)

        return unsat_rules

    def discover(self) -> List[set]:
        # To enforce fall-throughs
        if not ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            if "ArtificialNoneNode" in self.dfg.nodes:
                self.dfg.remove_node("ArtificialNoneNode")

        if "ArtificialNoneNode" in self.dfg.nodes and ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            return None
        if self.dfg is None or len(self.dfg.nodes) == 0:
            return None

        start_activities = set(
            n for n in self.dfg.nodes if self.dfg.nodes[n].get("start", 0) > 0
        )
        end_activities = set(
            n for n in self.dfg.nodes if self.dfg.nodes[n].get("end", 0) > 0
        )
        do = start_activities.union(end_activities)
        if len(do) == 0:
            raise ValueError(
                "No start or end activities found in the DFG, cannot apply LoopCut."
            )

        activities = set(self.dfg.nodes)
        groups = [do] + self.__reduce_dfg(do, activities)

        real_start_activities = start_activities.difference(end_activities)
        groups = self.__exclude_groups_not_reachable_from_start(
            self.dfg, groups, real_start_activities
        )
        real_end_activities = end_activities.difference(start_activities)
        groups = self.__exclude_groups_not_reachable_from_end(
            self.dfg, groups, real_end_activities
        )
        groups = self.merge_groups_with_start_activities(
            self.dfg, groups, start_activities
        )
        groups = self.merge_groups_with_end_activities(self.dfg, groups, end_activities)

        groups = [g for g in groups if g]
        if len(groups) <= 1:
            return None

        return [groups[0], set().union(*groups[1:])]

    def __reduce_dfg(self, do_partition: set, activities: set) -> List[set]:
        new_dfg = self.dfg.copy()
        for e, v in self.dfg.edges:
            # We get rid of all edges that are directly connected to the do_partition
            if e in do_partition or v in do_partition:
                new_dfg.remove_edge(e, v)
        resulting_activities = set(activities).difference(do_partition)
        # keep the dfg only with the resulting activities
        new_dfg = new_dfg.subgraph(resulting_activities)
        weakly_connected_components = nx.weakly_connected_components(new_dfg)
        groups = [set(component) for component in weakly_connected_components]
        return groups

    @staticmethod
    def __exclude_groups_not_reachable_from_start(
        dfg: nx.DiGraph, groups: List[set], start_activities: set
    ) -> List[set]:
        for act in start_activities:
            for e, v in dfg.edges:
                if e == act:
                    group_v = next((group for group in groups if v in group), None)
                    group_a = next((group for group in groups if act in group), None)
                    groups = [
                        group
                        for group in groups
                        if group != group_v and group != group_a
                    ]
                    groups.insert(0, group_v.union(group_a))
        return groups

    @staticmethod
    def __exclude_groups_not_reachable_from_end(
        dfg: nx.DiGraph, groups: List[set], end_activities: set
    ) -> List[set]:
        for act in end_activities:
            for e, v in dfg.edges:
                if v == act:
                    group_e = next((group for group in groups if e in group), None)
                    group_a = next((group for group in groups if act in group), None)
                    groups = [
                        group
                        for group in groups
                        if group != group_e and group != group_a
                    ]
                    groups.insert(0, group_e.union(group_a))
        return groups

    @staticmethod
    def merge_groups_with_start_activities(
        dfg: nx.DiGraph, groups: List[set], start_activities: set
    ) -> List[set]:
        i = 1
        dfg_edges = set(dfg.edges)

        while i < len(groups):
            merge = False
            for a in groups[i]:
                if merge:
                    break
                for x, b in dfg_edges:
                    if x == a and b in start_activities:
                        for s in start_activities:
                            if (a, s) not in dfg_edges:
                                merge = True
                                break
                        if merge:
                            break
            if merge:
                groups[0] = groups[0].union(groups[i])
                del groups[i]
                continue
            i += 1

        return groups

    @staticmethod
    def merge_groups_with_end_activities(
        dfg: nx.DiGraph, groups: List[set], end_activities: set
    ) -> List[set]:
        i = 1
        dfg_edges = set(dfg.edges)

        while i < len(groups):
            merge = False
            for a in groups[i]:
                if merge:
                    break
                for b, x in dfg_edges:
                    if x == a and b in end_activities:
                        for e in end_activities:
                            if (e, a) not in dfg_edges:
                                merge = True
                                break
                        if merge:
                            break
            if merge:
                groups[0] = groups[0].union(groups[i])
                del groups[i]
                continue
            i += 1

        return groups

    @staticmethod
    def project(
        log: List[List[str]], groups: List[set], **kwargs
    ) -> List[List[List[str]]]:
        do = groups[0]
        redo = groups[1:]
        redo_activities = {y for x in redo for y in x}

        do_log = []
        redo_logs = [[] for _ in range(len(redo))]

        for trace in log:
            do_trace = []
            redo_trace = []

            for act in trace:
                if act in do:
                    do_trace.append(act)
                    if len(redo_trace) > 0:
                        redo_logs = LoopCut._append_trace_to_redo_log(
                            redo_trace, redo_logs, redo
                        )
                        redo_trace = []
                elif act in redo_activities:
                    redo_trace.append(act)
                    if len(do_trace) > 0:
                        do_log.append(do_trace)
                        do_trace = []
            if len(redo_trace) > 0:
                redo_logs = LoopCut._append_trace_to_redo_log(
                    redo_trace, redo_logs, redo
                )

            do_log.append(do_trace)

        logs = [do_log]
        logs.extend(redo_logs)
        return logs

    from typing import List, Set

    @staticmethod
    def project(
        log: List[List[str]], groups: List[set], **kwargs
    ) -> List[List[List[str]]]:
        do = groups[0]
        redo = groups[1:]
        redo_activities = {y for x in redo for y in x}

        do_log = []
        redo_logs = [[] for _ in range(len(redo))]

        for trace in log:
            do_trace = []
            redo_trace = []

            for act in trace:
                if act in do:
                    do_trace.append(act)
                    if len(redo_trace) > 0:
                        redo_logs = LoopCut._append_trace_to_redo_log(
                            redo_trace, redo_logs, redo
                        )
                        redo_trace = []
                else:
                    if act in redo_activities:
                        redo_trace.append(act)
                        if len(do_trace) > 0:
                            do_log.append(do_trace)
                            do_trace = []

            if len(redo_trace) > 0:
                redo_logs = LoopCut._append_trace_to_redo_log(
                    redo_trace, redo_logs, redo
                )

            do_log.append(do_trace)

        logs = [do_log]
        logs.extend(redo_logs)
        return logs

    @staticmethod
    def _append_trace_to_redo_log(
        redo_trace: List[str],
        redo_logs: List[List[List[str]]],
        redo_groups: List[Set[str]],
    ) -> List[List[List[str]]]:
        activities = set(redo_trace)
        inte = [
            (i, len(activities.intersection(redo_groups[i])))
            for i in range(len(redo_groups))
        ]
        inte = sorted(inte, key=lambda x: (x[1], x[0]), reverse=True)
        redo_logs[inte[0][0]].append(redo_trace)
        return redo_logs


class BinaryLoopCut(LoopCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryLoopCut"

    def discover(self) -> List[set]:
        # Just call the super class on that
        groups = super().discover()
        return groups

    def project(
        self,
        log: List[List[str]],
        groups: List[set],
        activity_key: str = "concept:name",
        case_key: str = "case:concept:name",
    ) -> pd.DataFrame:
        # Just call the super class on that
        return super().project(
            log, groups, activity_key=activity_key, case_key=case_key
        )


if __name__ == "__main__":
    # try with <a>, <a,a,a>, <a,a,a,a,a>
    dfg = nx.DiGraph()
    dfg.add_edge("a", "a", weight=4)
    dfg.nodes["a"]["start"] = 5
    dfg.nodes["a"]["end"] = 5
    loop_cut = LoopCut(dfg)
    groups = loop_cut.discover()
    print(groups)
