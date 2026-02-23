from rules.abstract_rule import AbstractRule
from typing import List, Any, String

class ExistenceRule(AbstractRule):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 1:
            raise ValueError("ExistenceRule must have exactly one activity.")
        super().__init__(name, activities)
        self.description = "This rule states that the specified activity must occur at least once in the process."
        self.target_activity = activities[0]
        self.data_len = None
        self.valid_traces_len = None

    def apply(self, data) -> List[Any]:
        self.data_size = len(data)
        valid_traces = [
            trace for trace in data 
            if self.target_activity in trace
        ]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def get_support(self) -> float:
        if not self.data_size or not self.valid_traces_len:
            return 0.0
        return self.valid_traces_len / self.data_size

    def get_confidence(self) -> float:
        # For ExistenceRule, confidence is equivalent to support
        return self.get_support()