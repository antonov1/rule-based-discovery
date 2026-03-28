from typing import Any, List

from rules.abstract_rule import AbstractRule


class NotCoExistenceRule(AbstractRule):
    "This rule states that the two specified activities cannot coexist in the same trace."

    def __init__(self, activities: List[str]) -> None:
        if len(activities) != 2:
            raise ValueError("NotCoExistenceRule must have exactly two activities.")
        super().__init__(activities)
        self.name = "NotCoExistence"
        self.description = "This rule states that the two specified activities cannot coexist in the same trace."
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def __str__(self):
        return f"NotCoExistence({', '.join(self.activities)})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        valid_traces = []
        for trace in data:
            if not (self.activity_a in trace and self.activity_b in trace):
                valid_traces.append(trace)
        self.data_len = len(data)
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def calc_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        return self.sup

    def calc_confidence(self, data) -> float:
        count_a = sum(1 for trace in data if self.activity_a in trace)
        count_b = sum(1 for trace in data if self.activity_b in trace)
        if count_a == 0 and count_b == 0:
            return (
                1.0  # If both activities never occur, confidence is considered to be 1
            )
        count_ab = sum(
            1
            for trace in self.apply(data)
            if self.activity_a in trace and self.activity_b in trace
        )

        if count_a == 0:
            return 1 - count_ab / count_b

        if count_b == 0:
            return 1 - count_ab / count_a

        self.conf = max(1 - count_ab / count_a, 1 - count_ab / count_b)
        return self.conf
