from typing import Any, List

from rules.precedence import PrecedenceRule


class ChainPrecedenceRule(PrecedenceRule):
    "This rule states that the second activity can only occur if the first activity has occurred before it in the trace."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        super().__init__(activity_a, activity_b)
        self.description = (
            "This rule states that the second activity can only occur "
            "if the first activity has occurred directly before it in the trace."
        )

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)

        for trace in data:
            if self.activity_b in trace:
                index_b = trace.index(self.activity_b)
                if index_b > 0 and self.activity_a == trace[index_b - 1]:
                    valid_traces.append(trace)
            else:
                valid_traces.append(trace)

        self.valid_traces_len = len(valid_traces)
        return valid_traces
