from rules.abstract_rule import AbstractRule
from typing import List, Any, String


class ResponseRule(AbstractRule):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 2:
            raise ValueError("ResponseRule must have exactly two activities.")
        super().__init__(name, activities)
        self.description = "This rule states that if the first activity occurs, the second activity must eventually follow."
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)
        for trace in data:
            if self.activity_a in trace:
                index_a = trace.index(self.activity_a)
                if self.activity_b in trace[index_a + 1:]:
                    valid_traces.append(trace)
            else:
                valid_traces.append(trace)  # If activity A is not present, the rule is vacuously satisfied
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def get_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        return self.valid_traces_len / self.data_len

    def get_confidence(self, data) -> float:
        count_a = sum(1 for trace in data if self.activity_a in trace)
        if count_a == 0:
            return 1.0  # If activity A never occurs, confidence is considered to be 1
        count_ab = sum(1 for trace in self.apply(data) if self.activity_a in trace)
        return count_ab / count_a
