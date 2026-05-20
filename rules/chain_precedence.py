from typing import Any, List, Set

from automata.fa.dfa import DFA
from rules.precedence import PrecedenceRule


class ChainPrecedenceRule(PrecedenceRule):
    "This rule states that the second activity can only occur if the first activity has occurred before it in the trace."

    def __init__(self, activity_a: str, activity_b: str) -> None:
        if activity_a == activity_b:
            raise ValueError(
                "Activity A and B must be different for a chain precedence rule."
            )
        super().__init__(activity_a, activity_b)
        self.description = (
            "This rule states that the second activity can only occur "
            "if the first activity has occurred directly before it in the trace."
        )

    def apply(self, data) -> List[Any]:
        valid_traces = []
        self.data_len = len(data)

        for trace in data:
            is_valid = True

            for i, activity in enumerate(trace):
                if activity == self.activity_b:
                    if i == 0 or trace[i - 1] != self.activity_a:
                        is_valid = False
                        break

            if is_valid:
                valid_traces.append(trace)

        self.valid_traces_len = len(valid_traces)
        return valid_traces

    def repair(self, data) -> List[Any]:
        repaired = []

        for trace in data:
            new_trace = []

            for idx, act in enumerate(trace):
                if act == self.activity_b:
                    # add b's only in that case
                    if idx >= 1 and trace[idx - 1] == self.activity_a:
                        new_trace.append(act)
                else:
                    new_trace.append(act)

            repaired.append(new_trace)

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
            elif symbol == act_b:
                transitions[q0][symbol] = q2
            else:
                transitions[q0][symbol] = q0

            if symbol == act_a:
                transitions[q1][symbol] = q1
            elif symbol == act_b:
                transitions[q1][symbol] = q0
            else:
                transitions[q1][symbol] = q0

        return DFA(
            states={q0, q1, q2},
            input_symbols=set(alphabet),
            transitions=transitions,
            initial_state=q0,
            final_states={q0, q1},
        )


if __name__ == "__main__":
    rule = ChainPrecedenceRule("A", "B")
    log = [["A", "B"], ["B", "A"], ["A", "C", "B"], ["A", "A"]]
    print(rule.apply(log))
    print(rule.repair(log))
