from typing import List, Any, String, Optional
from abc import ABC, abstractmethod

class AtMostOnceRule(ABC):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 1:
            raise ValueError("AtMostOnceRule must have exactly one activity.")
        self.name = name
        self.description = "This rule states that the specified activity must occur at most once in the process."
        self.target_activity = activities[0]
        self.data_len = None
        self.valid_traces_len = None


    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        valid_traces = [
            trace for trace in data 
            if trace.count(self.target_activity) <= 1
        ]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def get_support(self) -> float:

        if not self.data_len:
            return 0.0
        return self.valid_traces_len / self.data_len

    def get_confidence(self) -> float:
        # For AtMostOnceRule, confidence is equivalent to support
        return self.get_support()