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
            is_valid = True

            for i, activity in enumerate(trace):
                if activity == self.activity_b:
                    if i == 0 or trace[i - 1] != self.activity_a:
                        is_valid = False
                        break

            if is_valid:
                valid_traces.append(trace)

        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []

        for trace in data:
            new_trace = []

            for idx, act in enumerate(trace):
                if act == self.activity_b:
                    # add b's only in that case
                    if idx >= 1 and trace[idx - 1] == self.activity_a:
                        new_trace.append(act)
                else:
                    new_trace.append(act)

            repaired.append(new_trace)

        return repaired
