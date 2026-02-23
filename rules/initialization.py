from rules.abstract_rule import AbstractRule
from typing import List, Any, String


class InitializationRule(AbstractRule):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 1:
            raise ValueError("InitializationRule must have exactly one activity.")
        super().__init__(name, activities)
        self.description = "This rule states that the process must start with the specified activity."
        self.target_activity = activities[0]
        self.data_len = None
        self.valid_traces_len = None

    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        self.valid_traces = [
            trace for trace in self.data 
            if trace and trace[0] == self.target_activity
        ]
        self.valid_traces_len = len(self.valid_traces)
        return self.valid_traces

    def get_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        return self.valid_traces_len / self.data_len
    

    def get_confidence(self) -> float:
        # For InitializationRule, confidence is equivalent to support
        return self.get_support()