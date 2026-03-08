from cuts.concurrent_cut import ConcurrentCut, BinaryConcurrentCut
from cuts.exclusive import ExclusiveChoiceCut, BinaryExclusiveChoiceCut
from cuts.loop_cut import LoopCut, BinaryLoopCut
import networkx as nx
import pandas as pd
from cuts.sequence import SequenceCut, BinarySequenceCut
from utils.directly_follows_graph import DirectlyFollowsGraph

# ====== TESTS FOR CONCURRENT CUT ======
def test_concurrent_cut_binary_simple():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case2', 'case2'],
        'concept:name': ['a', 'b', 'b', 'a'],
        'time:timestamp' : [1, 2, 1, 2]
    })
    dfg = DirectlyFollowsGraph(log).graph
    cut = BinaryConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {'a'} or set(groups[0]) == {'b'}
    assert set(groups[1]) == {'a'} or set(groups[1]) == {'b'}
    assert set(groups[0]).isdisjoint(set(groups[1]))
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a'} or set(sublog['concept:name'].unique()) == {'b'}

def test_concurrent_cut_3_groups():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case2', 'case2', 'case3', 'case3', 'case4', 'case4', 'case5', 'case5', 'case6', 'case6'],
        'concept:name': ['a', 'b', 'b', 'a', 'a', 'c', 'c', 'a', 'b', 'c', 'c', 'b'],
        'time:timestamp' : [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
    })
    # The binary concurrent cut
    dfg = DirectlyFollowsGraph(log).graph
    cut = BinaryConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 2
    print(groups)
    assert set(groups[0]) == {'c'}
    assert set(groups[1]) == {'b', 'a'}
    assert set(groups[0]).isdisjoint(set(groups[1]))
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'c'} or set(sublog['concept:name'].unique()) == {'b', 'a'}
    # Normal concurrent cut
    cut = ConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 3
    for group in groups:
        assert set(group) == {'c'} or set(group) == {'b'} or set(group) == {'a'}
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 3
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'c'} or set(sublog['concept:name'].unique()) == {'b'} or set(sublog['concept:name'].unique()) == {'a'}

# ====== TESTS FOR EXCLUSIVE CHOICE CUT ======

def test_exclusive_cut_0():
    test_log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case2', 'case2', 'case3', 'case3'],
        'concept:name': ['a', 'a', 'b', 'b', 'c', 'c'],
        'time:timestamp' : [1, 2, 1, 2, 1, 2]
    })
    dfg = DirectlyFollowsGraph(test_log).graph
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert len(partitions) == 3
    assert set(partitions[0]) == {'c'} 
    assert set(partitions[1]) == {'b'} 
    assert set(partitions[2]) == {'a'}
    # Test projection
    projected_logs = exclusive_cut.project(test_log, partitions)
    assert len(projected_logs) == 3
    assert projected_logs[0]['concept:name'].unique()[0] == 'c'
    assert len(projected_logs[0]) == 2
    assert projected_logs[1]['concept:name'].unique()[0] == 'b'
    assert len(projected_logs[1]) == 2
    assert projected_logs[2]['concept:name'].unique()[0] == 'a'
    assert len(projected_logs[2]) == 2


def test_exclusive_cut_0_binary():
    test_log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case2', 'case2', 'case3', 'case3'],
        'concept:name': ['a', 'a', 'b', 'b', 'c', 'c'],
        'time:timestamp' : [1, 2, 1, 2, 1, 2]
    })
    dfg = DirectlyFollowsGraph(test_log).graph
    exclusive_cut = BinaryExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert len(partitions) == 2
    assert set(partitions[0]) == {'c'} 
    assert set(partitions[1]) == {'b', 'a'}
    # Test projection
    projected_logs = exclusive_cut.project(test_log, partitions)
    assert len(projected_logs) == 2
    assert projected_logs[0]['concept:name'].unique()[0] == 'c'
    assert len(projected_logs[0]) == 2
    assert set(projected_logs[1]['concept:name'].unique()) == {'b', 'a'}
    assert len(projected_logs[1]) == 4


def test_exclusive_cut_1():
    dfg = nx.DiGraph()
    dfg.add_edges_from([
        ('A', 'B'),
        ('B', 'C'),
        ('D', 'E'),
        ('E', 'F'),
        ('C', 'E'),
        ('D', 'E')
    ])
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert len(partitions) == 1

def test_exclusive_cut_none():
    dfg = nx.DiGraph()
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    print(partitions)
    assert len(partitions) == 0

# ====== TESTS FOR LOOP CUT ======
def test_loop_cut_0():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case1', 'case2', 'case2', 'case2'],
        'concept:name': ['a', 'b', 'a', 'a', 'c', 'a'],
        'time:timestamp' : [1, 2, 3, 1, 2, 3]
    })
    dfg = DirectlyFollowsGraph(log).graph
    loop_cut = LoopCut(dfg)
    groups = loop_cut.discover()
    assert len(groups) == 3
    assert set(groups[0]) == {'a'}
    assert set(groups[1]) == {'b'} or set(groups[1]) == {'c'}
    assert set(groups[2]) == {'b'} or set(groups[2]) == {'c'}
    assert set(groups[2]) != set(groups[1])
    projected_logs = loop_cut.project(log, groups)
    print(projected_logs)
    assert len(projected_logs) == 3
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a'} or set(sublog['concept:name'].unique()) == {'b'} \
        or set(sublog['concept:name'].unique()) == {'c'}
def test_loop_cut_0_binary():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case1', 'case2', 'case2', 'case2'],
        'concept:name': ['a', 'b', 'a', 'a', 'c', 'a'],
        'time:timestamp' : [1, 2, 3, 1, 2, 3]
    })
    dfg = DirectlyFollowsGraph(log).graph
    loop_cut = BinaryLoopCut(dfg)
    groups = loop_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {'a'}
    assert set(groups[1]) == {'b', 'c'}
    projected_logs = loop_cut.project(log, groups)
    print(projected_logs)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a'} or set(sublog['concept:name'].unique()) == {'b', 'c'}

# ====== TESTS FOR SEQUENCE CUT ======

def test_sequence_cut_0():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case2', 'case2', 'case3', 'case3'],
        'concept:name': ['a', 'b', 'a', 'b', 'a', 'b'],
        'time:timestamp' : [1, 2, 1, 2, 1, 2]
    })
    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = SequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {'a'}
    assert set(groups[1]) == {'b'}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a'} or set(sublog['concept:name'].unique()) == {'b'}

def test_sequence_cut_1():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case1', 'case1'],
        'concept:name': ['a', 'b', 'c', 'd'],
        'time:timestamp' : [1, 2, 3, 4]
    })
    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = SequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 4
    assert set(groups[0]) == {'a'}
    assert set(groups[1]) == {'b'}
    assert set(groups[2]) == {'c'}
    assert set(groups[3]) == {'d'}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 4
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a'} or set(sublog['concept:name'].unique()) == {'b'} \
        or set(sublog['concept:name'].unique()) == {'c'} or set(sublog['concept:name'].unique()) == {'d'}

def test_sequence_cut_1_binary():
    log = pd.DataFrame({
        'case:concept:name': ['case1', 'case1', 'case1', 'case1'],
        'concept:name': ['a', 'b', 'c', 'd'],
        'time:timestamp' : [1, 2, 3, 4]
    })
    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = BinarySequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {'a', 'b'}
    assert set(groups[1]) == {'c', 'd'}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        assert set(sublog['concept:name'].unique()) == {'a', 'b'} or set(sublog['concept:name'].unique()) == {'c', 'd'}