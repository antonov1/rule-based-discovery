from rules.abstract_rule import AbstractRule
from typing import List, Any, String

class PrecedenceRule(AbstractRule):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 2:
            raise ValueError("PrecedenceRule must have exactly two activities.")
        super().__init__(name, activities)
        self.description = "This rule states that the second activity can only occur if the first activity has occurred directly it in the trace."
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)

        for trace in self.data:
            if self.activity_b in trace:
                index_b = trace.index(self.activity_b)
                if self.activity_a in trace[:index_b]:
                    valid_traces.append(trace)
            else:
                valid_traces.append(trace)  # If activity B is not present, the rule is satisfied
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def get_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        return self.valid_traces_len / self.data_len

    def get_confidence(self, data) -> float:
        count_b = sum(1 for trace in data if self.activity_b in trace)
        if count_b == 0:
            return 1.0  # If activity B never occurs, confidence is considered to be 1
        count_ab = sum(1 for trace in self.apply(data) if self.activity_b in trace)
        return count_ab / count_b