from abc import ABC, abstractmethod
from typing import Any, List, Union

from rules import (
    AbstractRule,
    CoExistenceRule,
    ExistenceRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)
from utils.directly_follows_graph import DirectlyFollowsGraph


class BaseCut(ABC):
    def __init__(
        self, name: str, activities: List[str], dfg: DirectlyFollowsGraph
    ) -> None:
        pass

    @abstractmethod
    def discover(self) -> List[Any]:
        pass

    @abstractmethod
    def project(self, trace: List[str], group: set) -> List[str]:
        pass

    @staticmethod
    def project_rules(
        rules: Union[List[AbstractRule], None], groups: List[set]
    ) -> List[AbstractRule]:
        if rules is None:
            return None
        projected_rules = [[] for _ in groups]
        for rule in rules:
            if isinstance(rule, AbstractRule):
                # check if it has target activity
                if hasattr(rule, "target_activity"):
                    for i in range(len(groups)):
                        if rule.target_activity in groups[i]:
                            projected_rules[i].append(rule)
                            break
                elif hasattr(rule, "activity_a") and hasattr(rule, "activity_b"):
                    group_a_idx = None
                    group_b_idx = None
                    for i in range(len(groups)):
                        if rule.activity_a in groups[i]:
                            group_a_idx = i
                        if rule.activity_b in groups[i]:
                            group_b_idx = i
                    if group_a_idx is None or group_b_idx is None:
                        # not relevant anymore
                        continue
                    if group_a_idx is not None and group_b_idx is not None:
                        if group_a_idx != group_b_idx:
                            # We have just eliminated a rule
                            if isinstance(rule, ResponseRule) or isinstance(
                                rule, RespondedExistenceRule
                            ):
                                # We need to make sure that the second rule occurs
                                # To avoid tricky situations
                                projected_rules[group_b_idx].append(
                                    ExistenceRule(rule.activity_b)
                                )
                            elif isinstance(rule, CoExistenceRule):
                                # Both should exist, otherwise, hard
                                projected_rules[group_a_idx].append(
                                    ExistenceRule(rule.activity_a)
                                )
                                projected_rules[group_b_idx].append(
                                    ExistenceRule(rule.activity_b)
                                )
                            elif isinstance(rule, PrecedenceRule):
                                projected_rules[group_a_idx].append(
                                    ExistenceRule(rule.activity_a)
                                )
                        else:
                            projected_rules[group_a_idx].append(rule)
        return projected_rules
