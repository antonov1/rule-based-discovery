from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.response import ResponseRule


class ChainResponseRule(ResponseRule):
    "This rule states that if the first activity occurs, the second activity must directly follow"

    def __init__(self, activity_a: str, activity_b: str) -> None:
        if activity_a == activity_b:
            raise ValueError(
                "Activity A and B must be different for a chain response rule."
            )
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
            is_valid = True
            if self.activity_a in trace:
                for i, act in enumerate(trace):
                    if act == self.activity_a:
                        if i == len(trace) - 1 or trace[i + 1] != self.activity_b:
                            is_valid = False
            if is_valid:
                valid_traces.append(trace)
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            repaired_trace = []
            for idx, act in enumerate(trace):
                if act == self.activity_a:
                    if idx < len(trace) - 1 and trace[idx + 1] == self.activity_b:
                        repaired_trace.append(act)
                else:
                    repaired_trace.append(act)
            repaired.append(repaired_trace)

        return repaired

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
            q0: {},
            q1: {},
            q2: {symbol: q2 for symbol in alphabet},
        }

        for symbol in alphabet:
            if symbol == act_a:
                transitions[q0][symbol] = q1
            else:
                transitions[q0][symbol] = q0

            if symbol == act_b:
                transitions[q1][symbol] = q0
            else:
                transitions[q1][symbol] = q2

        return DFA(
            states={q0, q1, q2},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q0},
        )
