from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.abstract_rule import AbstractRule


class NotCoExistenceRule(AbstractRule):
    "This rule states that the two specified activities cannot coexist in the same trace."

    def __init__(self, activity_a, activity_b) -> None:
        if activity_a == activity_b:
            raise ValueError(
                "Activity A and B must be different for a non-coexistence rule."
            )
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
        if count_a + count_b - count_ab == 0:
            self.conf = 1
            return 1
        self.conf = (count_a + count_b - count_ab) / (count_a + count_b)
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
        q3 = "q3"
        transitions = {
            q0: {
                symbol: q0 for symbol in alphabet if symbol != act_a and symbol != act_b
            },
            q1: {symbol: q1 for symbol in alphabet if symbol != act_b},
            q2: {symbol: q2 for symbol in alphabet if symbol != act_a},
            q3: {symbol: q3 for symbol in alphabet},
        }
        transitions[q0][act_a] = q1
        transitions[q0][act_b] = q2
        transitions[q1][act_b] = q3
        transitions[q2][act_a] = q3
        return DFA(
            states={q0, q1, q2, q3},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q0, q1, q2},
        )
