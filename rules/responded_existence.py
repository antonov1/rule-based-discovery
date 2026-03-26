from typing import Any, List

from rules.abstract_rule import AbstractRule


class RespondedExistenceRule(AbstractRule):
    "This rule states that if the first activity occurs, the second activity must also occur at least once in the trace."

    def __init__(self, activities: List[str]) -> None:
        if len(activities) != 2:
            raise ValueError("RespondedExistenceRule must have exactly two activities.")
        super().__init__(activities)
        self.description = "This rule states that if the first activity occurs, the second activity must also occur at least once in the trace."
        self.activity_a = activities[0]
        self.activity_b = activities[1]
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def __str__(self):
        return f"RespondedExistence({', '.join(self.activities)})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)
        for trace in data:
            if self.activity_a in trace:
                if self.activity_b in trace:
                    valid_traces.append(trace)
            else:
                valid_traces.append(
                    trace
                )  # If activity A is not present, the rule is vacuously satisfied
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
        count_ab = sum(1 for trace in self.apply(data) if self.activity_a in trace)
        self.conf = count_ab / count_a
        return self.conf
