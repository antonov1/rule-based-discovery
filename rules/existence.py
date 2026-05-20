from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.abstract_rule import AbstractRule


class ExistenceRule(AbstractRule):
    "This rule states that the specified activity must occur at least once in the process."

    def __init__(self, activity) -> None:
        super().__init__([activity])
        self.description = "This rule states that the specified activity must occur at least once in the process."
        self.target_activity = activity
        self.data_len = None
        self.valid_traces_len = None
        self.sup = 0
        self.conf = 0

    def apply(self, data) -> List[Any]:
        self.data_size = len(data)
        valid_traces = [trace for trace in data if self.target_activity in trace]
        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        # Repair here is just application
        return self.apply(data)

    def calc_support(self) -> float:
        if not self.data_size or not self.valid_traces_len:
            return 0.0
        self.sup = self.valid_traces_len / self.data_size
        self.conf = self.sup
        return self.sup

    def calc_confidence(self) -> float:
        # For ExistenceRule, confidence is equivalent to support
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
            q1: {symbol: q1 for symbol in alphabet},
        }
        transitions[q0][act] = q1
        return DFA(
            states={q0, q1},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q1},
        )
