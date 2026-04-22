from rules import *
from inductive_miner.main import *

if __name__ == "__main__":
    examples = [
        {
            "name": "1. Enforce existence even though part of the log misses A",
            "log": [["B"], ["A", "B"], ["B", "C"]],
            "rules": [ExistenceRule("A")],
            "why": "Some traces do not contain A, but the discovered model should require A.",
        },
        {
            "name": "2. Enforce at-most-once although the log repeats A",
            "log": [["A", "B", "A"], ["A"], ["B", "A", "C"]],
            "rules": [AtMostOnceRule("A")],
            "why": "The log contains repetitions of A, but the resulting model should not allow A more than once.",
        },
        {
            "name": "3. Enforce not-coexistence even though A and B co-occur in the log",
            "log": [["A"], ["B"], ["A", "B"], ["A"]],
            "rules": [NotCoExistenceRule("A", "B")],
            "why": "The trace ['A', 'B'] violates the rule, but the model should separate A and B so they cannot co-exist.",
        },
        {
            "name": "4. Enforce co-existence although the log has A without B",
            "log": [["A"], ["A", "B"], ["B"], ["A", "B"]],
            "rules": [CoExistenceRule("A", "B")],
            "why": "The log is inconsistent, but the model should enforce that A and B always appear together.",
        },
        {
            "name": "5. Enforce initialization although one trace starts with B",
            "log": [["B", "A"], ["A", "C"], ["A", "B"]],
            "rules": [InitializationRule("A")],
            "why": "The first trace violates the rule, but the model should start with A.",
        },
        {
            "name": "6. Enforce end rule although one trace ends with C",
            "log": [["A", "B"], ["C", "B"], ["A", "C"]],
            "rules": [EndRule("B")],
            "why": "Not all traces end in B, but the resulting model should.",
        },
        {
            "name": "7. Enforce precedence A -> B although B appears without A",
            "log": [["B"], ["A", "B"], ["C", "A", "B"]],
            "rules": [PrecedenceRule("A", "B")],
            "why": "The first trace violates precedence, but the model should require A before B.",
        },
        {
            "name": "8. Enforce response A -> B although some A is not followed by B",
            "log": [["A"], ["A", "C"], ["A", "B"], ["C"]],
            "rules": [ResponseRule("A", "B")],
            "why": "Some occurrences of A are not followed by B, but the model should enforce that they are.",
        },
        {
            "name": "9. Enforce responded existence A -> B although A occurs alone",
            "log": [["A"], ["A", "B"], ["C"], ["B"]],
            "rules": [RespondedExistenceRule("A", "B")],
            "why": "A appears without B in one trace, but the model should ensure that if A occurs, B occurs too.",
        },
        {
            "name": "10. Enforce not-succession A !-> B although the log contains A then B",
            "log": [["A", "B"], ["A", "C"], ["B"]],
            "rules": [NotSuccessionRule("A", "B")],
            "why": "The first trace violates the rule, but the model should disallow B after A.",
        },
        {
            "name": "11. Combine initialization and end with noisy traces",
            "log": [["B", "A"], ["A", "C"], ["A", "B"], ["A", "D", "C"]],
            "rules": [InitializationRule("A"), EndRule("C")],
            "why": "The first trace does not start with A and one trace ends with B, but the model should start with A and end with C.",
        },
        {
            "name": "12. Combine existence and at-most-once",
            "log": [["A", "B", "A"], ["B"], ["A", "C"]],
            "rules": [ExistenceRule("A"), AtMostOnceRule("A")],
            "why": "The model should require A, but also forbid repeating it.",
        },
        {
            "name": "13. Combine precedence and response",
            "log": [["B"], ["A"], ["A", "B"], ["C", "A", "D"]],
            "rules": [PrecedenceRule("A", "B"), ResponseRule("A", "B")],
            "why": "B should only happen after A, and every A should be followed by B, despite contradictory traces.",
        },
        {
            "name": "14. Combine not-coexistence with existence",
            "log": [["A"], ["B"], ["A", "B"], ["C"]],
            "rules": [ExistenceRule("A"), NotCoExistenceRule("A", "B")],
            "why": "The model should require A but still forbid A and B from appearing together.",
        },
        {
            "name": "15. Combine co-existence with initialization",
            "log": [["A"], ["B"], ["A", "B"], ["C", "A", "B"]],
            "rules": [InitializationRule("A"), CoExistenceRule("A", "B")],
            "why": "The model should start with A and enforce that A and B always occur together.",
        },
        {
            "name": "16. Initialization + co-existence + end, with noisy optional behavior",
            "log": [
                ["A", "B", "D", "E"],
                ["A", "B", "E"],
                ["B", "E"],  # violates initialization
                ["A", "D", "E"],  # violates co-existence
                ["A", "B", "D"],  # violates end
                ["C", "A", "B", "E"],  # violates initialization
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule("A", "B"),
                EndRule("E"),
            ],
            "why": (
                "A should always be the first activity, A and B should always appear together, "
                "and every valid execution should end in E. The log contains several traces "
                "that violate one or more of these constraints."
            ),
        },
        {
            "name": "17. Initialization + co-existence + at-most-once + not-succession",
            "log": [
                ["A", "B", "C"],
                ["A", "B", "D"],
                ["A", "B", "C", "B"],  # violates at-most-once(B)
                ["B", "A", "C"],  # violates initialization
                ["A", "C"],  # violates co-existence
                ["A", "B", "C", "D"],  # violates not-succession(C, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule("A", "B"),
                AtMostOnceRule("B"),
                NotSuccessionRule("C", "D"),
            ],
            "why": (
                "This one is more interesting because the rules interact: A must start, "
                "A and B must always occur together, B cannot repeat, and D must not come "
                "after C. The log contains traces that break each of these in different ways."
            ),
        },
        {
            "name": "18. Initialization + co-existence + response + not-coexistence",
            "log": [
                ["A", "B", "D"],
                ["A", "B", "C", "D"],  # violates not-coexistence(C, D)
                ["B", "D"],  # violates initialization
                ["A", "D"],  # violates co-existence
                ["A", "B"],  # violates response(B, D)
                ["A", "B", "C"],  # violates response(B, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule("A", "B"),
                ResponseRule("B", "D"),
                NotCoExistenceRule("C", "D"),
            ],
            "why": (
                "A must be first, A and B must occur together, every B must eventually be "
                "followed by D, and C and D must never appear together. This forces the "
                "model to balance positive and negative constraints at once."
            ),
        },
        {
            "name": "19. Initialization + co-existence + precedence + end",
            "log": [
                ["A", "B", "C", "E"],
                ["A", "B", "E"],
                ["B", "A", "E"],  # violates initialization
                ["A", "C", "E"],  # violates co-existence
                ["A", "B", "E", "C"],  # violates end
                ["A", "B", "D", "C", "E"],
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule("A", "B"),
                PrecedenceRule("B", "C"),
                EndRule("E"),
            ],
            "why": (
                "A must start, A and B must always occur together, C may only happen if B "
                "already happened, and E must be the end activity."
            ),
        },
        {
            "name": "20. Initialization + co-existence + responded existence + at-most-once",
            "log": [
                ["A", "B", "D"],
                ["A", "B"],
                ["A", "D"],  # violates co-existence
                ["B", "D"],  # violates initialization
                ["A", "B", "B", "D"],  # violates at-most-once(B)
                ["A", "B", "C"],  # violates responded existence(B, D)
            ],
            "rules": [
                InitializationRule("A"),
                CoExistenceRule("A", "B"),
                RespondedExistenceRule("B", "D"),
                AtMostOnceRule("B"),
            ],
            "why": (
                "Whenever B appears, D must also appear somewhere in the same trace; A and B "
                "must always occur together; A must be first; and B cannot repeat."
            ),
        },
        {
            "name": "21. One noisy event after the true end, with an optional middle branch",
            "log": [
                ["A", "B", "E"],
                ["A", "C", "E"],
                ["A", "B", "D", "E"],
                ["A", "C", "D", "E"],
                ["A", "B", "E", "X"],  # single noise event after the real end
            ],
            "rules": [
                InitializationRule("A"),
                EndRule("E"),
            ],
            "why": (
                "All clean traces support a structure like A -> optional choice/variation -> E. "
                "The last trace differs only by one extra event X after the true end E. "
                "A surgical repair can delete that one event and preserve the optional middle behavior. "
                "A subtrace-rejection strategy may instead treat the suffix after E as evidence for a larger "
                "or more rigid tail, or distort the decomposition around E."
            ),
        },
        {
            "name": "22. One duplicated B inside a stable A-B-optional-tail pattern",
            "log": [
                ["A", "B", "C"],
                ["A", "B", "D"],
                ["A", "B", "C", "D"],
                ["A", "B", "B", "C"],  # only one extra B
                ["A", "B"],
            ],
            "rules": [
                InitializationRule("A"),
                AtMostOnceRule("B"),
            ],
            "why": (
                "The clean traces all support a simple pattern where A starts, B occurs once, and then "
                "an optional tail follows. The violating trace has exactly one extra B in the middle. "
                "A surgical repair can remove that duplicate and keep the tail structure intact. "
                "A rejection-based approach may overreact by introducing a stricter sequence or collapsing "
                "the optional tail around the repeated region."
            ),
        },
        {
            "name": "23. Missing B after A in exactly one trace, while optional tail should survive",
            "log": [
                ["A", "B", "C"],
                ["A", "B", "D"],
                ["A", "B", "C", "D"],
                ["A", "C"],  # one missing B after A
                ["D"],
            ],
            "rules": [
                ResponseRule("A", "B"),
            ],
            "why": (
                "Most traces suggest that whenever A occurs, B should follow, while C and D remain optional tail behavior. "
                "The trace ['A', 'C'] is only one missing event away from compliance. "
                "A surgical repair can insert B and preserve the optional C tail. "
                "A subtrace-rejection approach may instead force a smaller model like A -> B and drop "
                "too much of the optional continuation."
            ),
        },
        {
            "name": "24. One accidental B violates not-coexistence, but the rest of the variant is useful",
            "log": [
                ["A", "C", "D"],
                ["A", "D"],
                ["B", "D"],
                ["B", "C", "D"],
                ["B", "A", "B", "C", "D"],
                ["A", "B"],
            ],
            "rules": [
                NotCoExistenceRule("A", "B"),
            ],
            "why": (
                "The log naturally suggests two families of behavior: an A-branch and a B-branch, both sharing useful "
                "continuation through C/D. The last trace violates not-coexistence only because of one accidental B. "
                "A surgical repair can delete that event and preserve the A-branch with its tail. "
                "A subtrace-rejection approach is more likely to separate A and B too aggressively and lose the shared "
                "tail structure or collapse to a very weak fallback model."
            ),
        },
        {
            "name": "25. Precedence violated by a single misplaced B before A",
            "log": [
                ["A", "B", "C"],
                ["D", "A", "B"],
                ["B", "A", "C", "B"],  # B is too early
                ["A", "C"],
            ],
            "rules": [PrecedenceRule("A", "B"), ChainResponseRule("B", "C")],
            "why": (
                "In ['B', 'A', 'C'], the problem is local: B occurs before A once. A surgical repair could "
                "move B after A or delete that early B. A subtrace-rejection approach is more likely to force "
                "a stricter decomposition that removes the optional C pattern or collapses the branch to A->B."
            ),
        },
    ]
    for ex in examples:
        print(f"\n--- {ex['name']} ---")
        print("Log:", ex["log"])
        print("Rules:", ex["rules"])
        print("Why:", ex["why"])
        model_constrainted = apply_IM_with_rules(ex["log"], ex["rules"])
        model_im = apply_IM(ex["log"])
        print(f"IM (no constraints): {model_im}")
        print(f"RIM: {model_constrainted}")
        print(
            f"Semantic similarity with IM (no constraints): {pm4py.behavioral_similarity(model_constrainted, model_im)}"
        )
