from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.abstract_rule import AbstractRule


class EndRule(AbstractRule):
    "This rule states that the process must start with the specified activity."

    def __init__(self, activity: str) -> None:
        super().__init__([activity])
        self.description = (
            "This rule states that the process must start with the specified activity."
        )
        self.target_activity = activity
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        self.data_len = len(data)
        self.valid_traces = [
            trace for trace in data if trace and trace[-1] == self.target_activity
        ]
        self.valid_traces_len = len(self.valid_traces)
        return self.valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []
        for trace in data:
            last_occurrence = (
                max([i for i in range(len(trace)) if trace[i] == self.target_activity])
                if self.target_activity in trace
                else None
            )
            # Trim the trace to the last occurrence
            if last_occurrence is not None:
                repaired.append(trace[: last_occurrence + 1])
        return repaired

    def calc_support(self) -> float:
        if not self.data_len or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_len
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For InitializationRule, confidence is equivalent to support
        self.conf = self.calc_support()
        return self.conf

    def to_automaton(self, alphabet: Set[str]) -> DFA:
        act = self.target_activity
        if act not in alphabet:
            raise ValueError(f"activity {act!r} is not in alphabet {alphabet}")
        q0 = "q0"  # initial state
        q1 = "q1"  # accepting state

        transitions = {
            q0: {symbol: q0 for symbol in alphabet if symbol != act},
            q1: {symbol: q0 for symbol in alphabet if symbol != act},
        }
        transitions[q0][act] = q1
        transitions[q1][act] = q1
        return DFA(
            states={q0, q1},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q1},
        )
