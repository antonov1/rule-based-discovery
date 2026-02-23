from rules.abstract_rule import AbstractRule
from rules.coexistence import CoExistenceRule
from typing import List, Any, String

class NotCoExistenceRule(AbstractRule):
    def __init__(self, name: String, activities: List[String]) -> None:
        if len(activities) != 2:
            raise ValueError("NotCoExistenceRule must have exactly two activities.")
        super().__init__(name, activities)
        self.description = "This rule states that the two specified activities cannot coexist in the same trace."
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None

    def apply(self, data) -> List[Any]:
        valid_traces = []
        for trace in data:
            if not (self.activity_a in trace and self.activity_b in trace):
                valid_traces.append(trace)
        self.data_len = len(data)
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def get_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        return self.valid_traces_len / self.data_len

    def get_confidence(self, data) -> float:
        count_a = sum(1 for trace in data if self.activity_a in trace)
        count_b = sum(1 for trace in data if self.activity_b in trace)
        if count_a == 0 and count_b == 0:
            return 1.0  # If both activities never occur, confidence is considered to be 1
        count_ab = sum(1 for trace in self.apply(data) if self.activity_a in trace and self.activity_b in trace)

        if count_a == 0:
            return 1 - count_ab / count_b
        
        if count_b == 0:
            return 1 - count_ab / count_a

        return max(1 - count_ab / count_a, 1 - count_ab / count_b)
        


        
