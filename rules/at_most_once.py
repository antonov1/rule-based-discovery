from typing import Any, List

from rules.abstract_rule import AbstractRule


class AtMostOnceRule(AbstractRule):
    "This rule states that the specified activity must occur at most once in the process."

    def __init__(self, activity: str) -> None:
        super().__init__([activity])

        self.description = "This rule states that the specified activity must occur at most once in the process."
        self.target_activity = activity
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        valid_traces = [
            trace for trace in data if trace.count(self.target_activity) <= 1
        ]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            occurrences = [
                i for i in range(len(trace)) if trace[i] == self.target_activity
            ]
            new_trace = trace
            if len(occurrences) > 1:
                # Remove everything apart from the first appearance
                to_remove = set(occurrences[1:])
                new_trace = [act for i, act in enumerate(trace) if i not in to_remove]
            repaired.append(new_trace)
        return repaired

    def calc_support(self) -> float:

        if not self.data_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For AtMostOnceRule, confidence is equivalent to support
        self.conf = self.calc_support()
        return self.conf
