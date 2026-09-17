from abc import ABC, abstractmethod
from typing import Any, List, Union

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
            # check if it has target activity
            if hasattr(rule, "target_activity"):
                projected = False
                for i in range(len(groups)):
                    if rule.target_activity in groups[i]:
                        projected_rules[i].append(rule)
                        projected = True
                        break
                if not projected:
                    projected_rules[0].append(rule)
            elif hasattr(rule, "activity_a") and hasattr(rule, "activity_b"):
                group_a_idx = None
                group_b_idx = None
                for i in range(len(groups)):
                    if rule.activity_a in groups[i]:
                        group_a_idx = i
                    if rule.activity_b in groups[i]:
                        group_b_idx = i
                if group_a_idx is None or group_b_idx is None:
                    if group_a_idx is not None:
                        (
                            projected_rules[group_a_idx].append(rule)
                            if not isinstance(
                                rule, (NotCoExistenceRule, NotSuccessionRule)
                            )
                            else None
                        )
                    elif group_b_idx is not None:
                        (
                            projected_rules[group_b_idx].append(rule)
                            if not isinstance(
                                rule, (NotCoExistenceRule, NotSuccessionRule)
                            )
                            else None
                        )
                if group_a_idx is not None and group_b_idx is not None:
                    if group_a_idx != group_b_idx:
                        # We have just eliminated a rule
                        if isinstance(rule, ChainResponseRule):
                            projected_rules[group_b_idx].append(
                                InitializationRule(rule.activity_b)
                            )
                            projected_rules[group_a_idx].extend(
                                [
                                    AtMostOnceRule(rule.activity_a),
                                    EndRule(rule.activity_a),
                                ]
                            )

                        elif isinstance(rule, ChainPrecedenceRule):
                            projected_rules[group_a_idx].append(
                                EndRule(rule.activity_a)
                            )
                            projected_rules[group_b_idx].extend(
                                [
                                    AtMostOnceRule(rule.activity_b),
                                    InitializationRule(rule.activity_b),
                                ]
                            )

                        elif isinstance(rule, ResponseRule) or isinstance(
                            rule, RespondedExistenceRule
                        ):
                            # We need to make sure that the second rule occurs
                            # To avoid tricky situations
                            projected_rules[group_b_idx].append(
                                ExistenceRule(rule.activity_b)
                            )
                            # if isinstance(rule, RespondedExistenceRule):
                            #    projected_rules[group_a_idx].append(
                            #        ExistenceRule(rule.activity_a)
                            #   )
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
