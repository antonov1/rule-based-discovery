from typing import Any, List

from rules.response import ResponseRule


class ChainResponseRule(ResponseRule):
    "This rule states that if the first activity occurs, the second activity must directly follow"

    def __init__(self, activity_a: str, activity_b: str) -> None:
        super().__init__(activity_a, activity_b)
        self.description = "This rule states that if the first activity occurs, the second activity must directly follow."

    def __str__(self):
        return f"ChainResponse({self.activity_a}, {self.activity_b})"

    def __repr__(self):
        return self.__str__()

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)
        for trace in data:
            if self.activity_a in trace:
                index_a = trace.index(self.activity_a)
                if index_a > 0 and trace[index_a] == self.activity_b:
                    valid_traces.append(trace)
            else:
                valid_traces.append(
                    trace
                )  # If activity A is not present, the rule is vacuously satisfied
        self.valid_traces_len = len(valid_traces)
        return valid_traces
