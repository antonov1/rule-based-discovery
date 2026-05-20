from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.abstract_rule import AbstractRule


class NotSuccessionRule(AbstractRule):
    "This rule states that the activity B does not follow the activity A."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        if activity_a == activity_b:
            raise ValueError(
                "Activity A and B must be different for a not succession rule. Use AtMost1 instead."
            )
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
        if count_a == 0:
            self.conf = 0
            return 0

        count_a_not_followed_by_b = 0
        for trace in data:
            if self.activity_a not in trace:
                continue
            first_occurrence_a = min(
                i for i, activity in enumerate(trace) if activity == self.activity_a
            )
            if self.activity_b not in trace:
                count_a_not_followed_by_b += 1
                continue
            last_occurrence_b = max(
                i for i, activity in enumerate(trace) if activity == self.activity_b
            )
            if last_occurrence_b < first_occurrence_a:
                count_a_not_followed_by_b += 1
        self.conf = count_a_not_followed_by_b / count_a
        return self.conf

    def to_automaton(self, alphabet: Set[str]) -> DFA:
        act_a = self.activity_a
        act_b = self.activity_b

        if act_a not in alphabet:
            raise ValueError(f"activity_a {act_a!r} is not in alphabet {alphabet}")

        if act_b not in alphabet:
            raise ValueError(f"activity_b {act_b!r} is not in alphabet {alphabet}")

        q0 = "q0"
        q1 = "q1"
        q2 = "q2"
        transitions = {
            q0: {symbol: q0 for symbol in alphabet if symbol != act_a},
            q1: {symbol: q1 for symbol in alphabet if symbol != act_b},
            q2: {symbol: q2 for symbol in alphabet},
        }
        transitions[q0][act_a] = q1
        transitions[q1][act_b] = q2
        return DFA(
            states={q0, q1, q2},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q0, q1},
        )
