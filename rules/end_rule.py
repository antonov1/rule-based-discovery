from typing import Any, List

from rules.abstract_rule import AbstractRule


class EndRule(AbstractRule):
    def __init__(self, activities: List[str]) -> None:
        if len(activities) != 1:
            raise ValueError("EndRule must have exactly one activity.")
        super().__init__(activities)
        self.description = (
            "This rule states that the process must start with the specified activity."
        )
        self.target_activity = activities[0]
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def __str__(self):
        return f"End({self.target_activity})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        self.valid_traces = [
            trace for trace in data if trace and trace[0] == self.target_activity
        ]
        self.valid_traces_len = len(self.valid_traces)
        return self.valid_traces

    def calc_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For InitializationRule, confidence is equivalent to support
        self.conf = self.calc_support()
        return self.conf
