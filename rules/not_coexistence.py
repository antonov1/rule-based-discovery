from typing import Any, List

from rules.abstract_rule import AbstractRule


class NotCoExistenceRule(AbstractRule):
    "This rule states that the two specified activities cannot coexist in the same trace."

    def __init__(self, activity_a, activity_b) -> None:
        super().__init__([activity_a, activity_b])
        self.description = "This rule states that the two specified activities cannot coexist in the same trace."
        self.activity_a = activity_a
        self.activity_b = activity_b
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        valid_traces = []
        for trace in data:
            if not (self.activity_a in trace and self.activity_b in trace):
                valid_traces.append(trace)
        self.data_len = len(data)
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            new_trace = trace
            if self.activity_a in trace and self.activity_b in trace:
                trace_idx_a = trace.index(self.activity_a)
                trace_idx_b = trace.index(self.activity_b)
                if trace_idx_a < trace_idx_b:
                    # If a is before b, we remove b's
                    new_trace = [act for act in trace if act != self.activity_b]
                else:
                    new_trace = [act for act in trace if act != self.activity_a]
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
        count_ab = sum(
            1
            for trace in self.apply(data)
            if self.activity_a in trace and self.activity_b in trace
        )
        self.conf = (count_a + count_b - count_ab) / (count_a + count_b)
        return self.conf
