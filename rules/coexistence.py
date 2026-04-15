from typing import Any, List

from rules.abstract_rule import AbstractRule


class CoExistenceRule(AbstractRule):
    "This rule states that the two specified activities must coexist in the same trace."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        super().__init__([activity_a, activity_b])
        self.description = "This rule states that the two specified activities must coexist in the same trace."
        self.activity_a = activity_a
        self.activity_b = activity_b
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)
        for trace in data:
            if self.activity_a in trace and self.activity_b in trace:
                valid_traces.append(trace)
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            new_trace = trace
            if self.activity_a in new_trace and self.activity_b not in new_trace:
                # remove a's
                new_trace = [act for act in trace if act != self.activity_a]
            elif self.activity_b in new_trace and self.activity_a not in new_trace:
                # remove b's
                new_trace = [act for act in trace if act != self.activity_b]
            repaired.append(new_trace)
        return repaired

    def calc_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        return self.sup

    def calc_confidence(self, data) -> float:
        count_a = sum(1 for trace in data if self.activity_a in trace)
        count_b = sum(1 for trace in data if self.activity_b in trace)
        count_ab = self.valid_traces_len
        # A u B
        activated = count_a + count_b - count_ab
        if activated == 0:
            return 1
        return count_ab / activated
