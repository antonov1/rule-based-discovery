from utils.directly_follows_graph import DirectlyFollowsGraph

"""
def test_dfg_construction():
    log = [['A', 'B', 'C'], ['A', 'C'], ['B', 'C'], []]
    dfg = DirectlyFollowsGraph(log)
    assert dfg.relations == {
        (None, 'A'): 2,
        ('A', 'B'): 1,
        (None, 'B'): 1,
        ('B', 'C'): 2,
        ('A', 'C'): 1,
        ('C', None): 3,
        (None, None): 1
    }
"""