from typing import Any, List

from rules.abstract_rule import AbstractRule


class NotSuccessionRule(AbstractRule):
    "This rule states that the activity B does not follow the activity A."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        super().__init__([activity_a, activity_b])
        self.description = (
            "This rule states that the activity B does not follow the activity A."
        )
        self.activity_a = activity_a
        self.activity_b = activity_b
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        valid_traces = []
        for trace in data:
            if self.activity_a not in trace or self.activity_b not in trace:
                valid_traces.append(trace)
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

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            new_trace = []
            for idx, act in enumerate(trace):
                if act == self.activity_a and self.activity_b in trace[idx + 1 :]:
                    continue
                new_trace.append(act)
            repaired.append(new_trace)
        return repaired

    def calc_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        return self.sup

    def calc_confidence(self, data) -> float:
        count_a = sum(1 for trace in data if self.activity_a in trace)
        count_a_not_followed_by_b = 0
        for trace in data:
            first_occurrence_a = min(
                [i for i in range(len(trace)) if trace[i] == self.activity_a]
            )
            last_occurrence_b = max(
                [i for i in range(len(trace)) if trace[i] == self.activity_b]
            )
            if last_occurrence_b < first_occurrence_a:
                count_a_not_followed_by_b += 1
        return count_a_not_followed_by_b / count_a
