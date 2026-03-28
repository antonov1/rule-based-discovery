from typing import Any, List

from rules.abstract_rule import AbstractRule


class AtMostOnceRule(AbstractRule):
    "This rule states that the specified activity must occur at most once in the process."

    def __init__(self, activities: List[str]) -> None:
        if len(activities) != 1:
            raise ValueError("AtMostOnceRule must have exactly one activity.")
        super().__init__(activities)

        self.name = "AtMostOnce"
        self.description = "This rule states that the specified activity must occur at most once in the process."
        self.target_activity = activities[0]
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def __str__(self):
        return f"AtMost1({self.target_activity})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        valid_traces = [
            trace for trace in data if trace.count(self.target_activity) <= 1
        ]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def calc_support(self) -> float:

        if not self.data_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For AtMostOnceRule, confidence is equivalent to support
        self.conf = self.calc_support()
        return self.conf
