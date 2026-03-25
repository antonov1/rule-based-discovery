from typing import Any, List

from rules.abstract_rule import AbstractRule


class NotSuccessionRule(AbstractRule):
    def __init__(self, activities: List[str]) -> None:
        if len(activities) != 2:
            raise ValueError("NotSuccessionRule must have exactly two activities.")
        super().__init__(activities)
        self.description = (
            "This rule states that the activity B does not follow the activity A."
        )
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def __str__(self):
        return f"NotSuccession({', '.join(self.activities)})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        valid_traces = []
        for trace in data:
            if self.activity_a not in trace or self.activity_b not in trace:
                continue
            else:
                first_occurrence_a = min(
                    [i for i in range(len(trace)) if trace[i] == self.activity_a]
                )
                last_occurrence_b = max(
                    [i for i in range(len(trace)) if trace[i] == self.activity_b]
                )
                if first_occurrence_a > last_occurrence_b:
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
        if count_a == 0:
            return 1.0  # If activity A never occurs, confidence is considered to be 1
        return self.calc_support() / count_a
