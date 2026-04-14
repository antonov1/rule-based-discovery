from typing import Any, List

from rules.abstract_rule import AbstractRule


class InitializationRule(AbstractRule):
    "This rule states that the process must start with the specified activity."

    def __init__(self, activity: str) -> None:
        super().__init__([activity])
        self.description = (
            "This rule states that the process must start with the specified activity."
        )
        self.target_activity = activity
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

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
