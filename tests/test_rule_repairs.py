from rules import *

# ----- UNARY RULES ------


def test_at_most_once():
    rule = AtMostOnceRule("A")
    log = [["A", "B", "A", "A"]]
    assert rule.repair(log) == [["A", "B"]]


def test_init():
    rule = InitializationRule("A")
    log = [[], ["C", "F", "G", "A", "B", "C"]]
    assert rule.repair(log) == [["A", "B", "C"]]


def test_end():
    rule = EndRule("Z")
    log = [["R"], ["A", "B", "Z", "Q"]]
    assert rule.repair(log) == [["A", "B", "Z"]]


def test_existence():
    rule = ExistenceRule("A")
    log = [["Q"], ["Z", "D", "A"]]
    assert rule.repair(log) == [["Z", "D", "A"]]


# ----- BINARY RULES ------
def test_chain_precedence():
    rule = ChainPrecedenceRule("A", "B")
    log = [["A", "B", "C", "B"]]
    assert rule.repair(log) == [["A", "B", "C"]]


def test_precedence():
    rule = PrecedenceRule("A", "B")
    log = [["B", "A", "B", "C", "B"]]
    assert rule.repair(log) == [["A", "B", "C", "B"]]


def test_chain_response():
    rule = ChainResponseRule("A", "B")
    log = [["A", "B", "A", "D", "B"], []]
    assert rule.repair(log) == [["A", "B", "D", "B"], []]


def test_response():
    rule = ResponseRule("A", "B")
    log = [["A", "B", "A", "D", "B", "A"], []]
    assert rule.repair(log) == [["A", "B", "A", "D", "B"], []]


def test_responded_existence():
    rule = RespondedExistenceRule("A", "B")
    log = [["A", "C", "D", "C"]]
    assert rule.repair(log) == [["C", "D", "C"]]


def test_coexistence():
    rule = CoExistenceRule("Z", "B")
    log = [["Q", "N", "A"], ["Z", "P"]]
    assert rule.repair(log) == [["Q", "N", "A"], ["P"]]


def test_not_succ():
    rule = NotSuccessionRule("A", "B")
    log = [["T", "R", "A", "L"], ["Q", "B", "A", "B"], []]
    assert rule.repair(log) == [["T", "R", "A", "L"], ["Q", "B", "B"], []]


def test_not_coex():
    rule = NotCoExistenceRule("A", "B")
    log = [["Q", "B", "A", "C"], ["A", "B"], []]
    assert rule.repair(log) == [["Q", "B", "C"], ["A"], []]
