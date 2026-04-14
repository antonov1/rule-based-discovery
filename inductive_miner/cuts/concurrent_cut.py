from typing import List

import networkx as nx
import pandas as pd
from inductive_miner.cuts.base_cut import BaseCut
from inductive_miner.cuts.cut_utils import ENABLE_EXPLICIT_EMPTY_TRACE_CHECK
from rules import (
    AbstractRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    EndRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    ResponseRule,
)


class ConcurrentCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("ConcurrentCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    @staticmethod
    def check_rules(rules: List[AbstractRule], groups: List[set]) -> bool:
        unsat_rules = []
        for rule in rules:
            if isinstance(rule, InitializationRule) or isinstance(rule, EndRule):
                if any(rule.target_activity in group for group in groups):
                    unsat_rules.append(rule)
            elif (
                isinstance(rule, NotCoExistenceRule)
                or isinstance(rule, NotSuccessionRule)
                or isinstance(rule, PrecedenceRule)
                or isinstance(rule, ChainPrecedenceRule)
                or isinstance(rule, ResponseRule)
                or isinstance(rule, ChainResponseRule)
            ):
                group_a = next(
                    (group for group in groups if rule.activity_a in group), None
                )
                group_b = next(
                    (group for group in groups if rule.activity_b in group), None
                )
                if group_a is not None and group_b is not None and group_a != group_b:
                    print(
                        f"Rule {rule} is not satisfied by the concurrent cut with groups {groups}"
                    )
                    unsat_rules.append(rule)
        return unsat_rules

    def discover(self) -> List[set]:
        # The workflow looks like this
        # 0. Create a set/group for each activity
        # 1. Merge not-fully connected sets
        # 2. Merge sets without start/end activities

        if not ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            if "ArtificialNoneNode" in self.dfg.nodes:
                self.dfg.remove_node("ArtificialNoneNode")

        if "ArtificialNoneNode" in self.dfg.nodes and ENABLE_EXPLICIT_EMPTY_TRACE_CHECK:
            return None

        alphabet = sorted(list(self.dfg.nodes))
        edges = sorted(list(self.dfg.edges))

        groups = [{a} for a in alphabet]
        if len(groups) == 0:
            return None

        cont = True
        while cont:
            cont = False
            i = 0
            while i < len(groups):
                j = i + 1
                while j < len(groups):
                    should_merge = False
                    for act1 in groups[i]:
                        for act2 in groups[j]:
                            if (act1, act2) not in edges or (act2, act1) not in edges:
                                should_merge = True
                                break
                        if should_merge:
                            break

                    if should_merge:
                        groups[i] = groups[i].union(groups[j])
                        del groups[j]
                        cont = True
                        break
                    else:
                        j += 1

                if cont:
                    break
                i += 1

        start_activities = set(
            n for n in self.dfg.nodes if self.dfg.nodes[n].get("start", 0) > 0
        )
        end_activities = set(
            n for n in self.dfg.nodes if self.dfg.nodes[n].get("end", 0) > 0
        )

        groups = list(sorted(groups, key=lambda g: len(g)))

        i = 0
        while i < len(groups) and len(groups) > 1:
            if groups[i].intersection(start_activities) and groups[i].intersection(
                end_activities
            ):
                i += 1
                continue

            group = groups[i]
            del groups[i]

            if i == 0:
                groups[i].update(group)
            else:
                groups[i - 1].update(group)

        return groups if len(groups) > 1 else None

    @staticmethod
    def project(
        event_log: List[List[str]], groups: List[set], **kwargs
    ) -> pd.DataFrame:
        sublogs = [[] for _ in range(len(groups))]
        for trace in event_log:
            for idx, group in enumerate(groups):
                sublogs[idx].append([act for act in trace if act in group])
        return sublogs


class BinaryConcurrentCut(ConcurrentCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryConcurrentCut"

    def discover(self) -> List[set]:
        # Just call the super class on that
        groups = super().discover()
        # Split them in a way s.t. the biggest group is one and the rest of the groups are merged into another
        if groups is not None and len(groups) > 2:
            # create a string out of each group based on the sorted activities in the group and sort them based on length
            merged_group = set()
            for group in groups[1:]:
                merged_group.update(group)
            groups = [groups[0], merged_group]
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
