from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.abstract_rule import AbstractRule


class RespondedExistenceRule(AbstractRule):
    "This rule states that if the first activity occurs, the second activity must also occur at least once in the trace."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        if activity_a == activity_b:
            raise ValueError(
                "Activity A and B must be different for a responded existence rule."
            )
        super().__init__([activity_a, activity_b])
        self.description = "This rule states that if the first activity occurs, the second activity must also occur at least once in the trace."
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
            if self.activity_a in trace:
                if self.activity_b in trace:
                    valid_traces.append(trace)
            else:
                valid_traces.append(
                    trace
                )  # If activity A is not present, the rule is vacuously satisfied
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            new_trace = trace
            if self.activity_a in trace and self.activity_b not in trace:
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
        if count_a == 0:
            return 1.0  # If activity A never occurs, confidence is considered to be 1
        count_ab = sum(1 for trace in self.apply(data) if self.activity_a in trace)
        self.conf = count_ab / count_a
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
            final_states={q0, q2, q3},
        )
