from typing import Any, List

from rules.abstract_rule import AbstractRule


class ExistenceRule(AbstractRule):
    "This rule states that the specified activity must occur at least once in the process."

    def __init__(self, activity) -> None:
        super().__init__([activity])
        self.description = "This rule states that the specified activity must occur at least once in the process."
        self.target_activity = activity
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        self.data_size = len(data)
        valid_traces = [trace for trace in data if self.target_activity in trace]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        # Repair here is just application
        return self.apply(data)

    def calc_support(self) -> float:
        if not self.data_size or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_size
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For ExistenceRule, confidence is equivalent to support
        self.conf = self.calc_support()
        return self.conf
