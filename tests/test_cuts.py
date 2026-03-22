import networkx as nx
import pandas as pd
from inductive_miner.cuts.concurrent_cut import BinaryConcurrentCut, ConcurrentCut
from inductive_miner.cuts.exclusive import BinaryExclusiveChoiceCut, ExclusiveChoiceCut
from inductive_miner.cuts.loop_cut import BinaryLoopCut, LoopCut
from inductive_miner.cuts.sequence import BinarySequenceCut, SequenceCut
from utils.directly_follows_graph import DirectlyFollowsGraph


# ====== TESTS FOR CONCURRENT CUT ======
def test_concurrent_cut_binary_simple():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case2", "case2"],
            "concept:name": ["a", "b", "b", "a"],
            "time:timestamp": [1, 2, 1, 2],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    dfg = DirectlyFollowsGraph(log).graph
    print(dfg.edges(data=True))
    cut = BinaryConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {"a"} or set(groups[0]) == {"b"}
    assert set(groups[1]) == {"a"} or set(groups[1]) == {"b"}
    assert set(groups[0]).isdisjoint(set(groups[1]))
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b"}


def test_concurrent_cut_3_groups():
    log = pd.DataFrame(
        {
            "case:concept:name": [
                "case1",
                "case1",
                "case2",
                "case2",
                "case3",
                "case3",
                "case4",
                "case4",
                "case5",
                "case5",
                "case6",
                "case6",
            ],
            "concept:name": [
                "a",
                "b",
                "b",
                "a",
                "a",
                "c",
                "c",
                "a",
                "b",
                "c",
                "c",
                "b",
            ],
            "time:timestamp": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    # The binary concurrent cut
    dfg = DirectlyFollowsGraph(log).graph
    cut = BinaryConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 2
    print(groups)
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b", "c"}
    assert set(groups[0]).isdisjoint(set(groups[1]))
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b", "c"}
    # Normal concurrent cut
    cut = ConcurrentCut(dfg)
    groups = cut.discover()
    assert len(groups) == 3
    for group in groups:
        assert set(group) == {"a"} or set(group) == {"b"} or set(group) == {"c"}
    projected_logs = cut.project(log, groups)
    assert len(projected_logs) == 3
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b"} or set(acts) == {"c"}


# ====== TESTS FOR EXCLUSIVE CHOICE CUT ======


def test_exclusive_cut_0():
    test_log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case2", "case2", "case3", "case3"],
            "concept:name": ["a", "a", "b", "b", "c", "c"],
            "time:timestamp": [1, 2, 1, 2, 1, 2],
        }
    )
    test_log = (
        test_log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    )
    dfg = DirectlyFollowsGraph(test_log).graph
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert len(partitions) == 3
    assert set(partitions[0]) == {"a"}
    assert set(partitions[1]) == {"b"}
    assert set(partitions[2]) == {"c"}
    # Test projection
    projected_logs = exclusive_cut.project(test_log, partitions)
    assert len(projected_logs) == 3
    acts_0 = {act for trace in projected_logs[0] for act in trace}
    assert set(acts_0) == {"a"}
    acts_1 = {act for trace in projected_logs[1] for act in trace}
    assert set(acts_1) == {"b"}
    acts_2 = {act for trace in projected_logs[2] for act in trace}
    assert set(acts_2) == {"c"}


def test_exclusive_cut_0_binary():
    test_log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case2", "case2", "case3", "case3"],
            "concept:name": ["a", "a", "b", "b", "c", "c"],
            "time:timestamp": [1, 2, 1, 2, 1, 2],
        }
    )
    test_log = (
        test_log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    )
    dfg = DirectlyFollowsGraph(test_log).graph
    exclusive_cut = BinaryExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert len(partitions) == 2
    assert set(partitions[0]) == {"a"}
    assert set(partitions[1]) == {"b", "c"}
    # Test projection
    projected_logs = exclusive_cut.project(test_log, partitions)
    assert len(projected_logs) == 2
    acts_0 = {act for trace in projected_logs[0] for act in trace}
    assert set(acts_0) == {"a"}
    acts_1 = {act for trace in projected_logs[1] for act in trace}
    assert set(acts_1) == {"b", "c"}
    print(projected_logs)
    total_length = sum(len(trace) for sublog in projected_logs[1] for trace in sublog)
    assert total_length == 4


def test_exclusive_cut_1():
    dfg = nx.DiGraph()
    dfg.add_edges_from(
        [("A", "B"), ("B", "C"), ("D", "E"), ("E", "F"), ("C", "E"), ("D", "E")]
    )
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    assert partitions is None


def test_exclusive_cut_none():
    dfg = nx.DiGraph()
    exclusive_cut = ExclusiveChoiceCut(dfg)
    partitions = exclusive_cut.discover()
    print(partitions)
    assert partitions is None


# ====== TESTS FOR LOOP CUT ======
def test_loop_cut_0():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case1", "case2", "case2", "case2"],
            "concept:name": ["a", "b", "a", "a", "c", "a"],
            "time:timestamp": [1, 2, 3, 1, 2, 3],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    dfg = DirectlyFollowsGraph(log).graph
    loop_cut = LoopCut(dfg)
    groups = loop_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b", "c"}
    projected_logs = loop_cut.project(log, groups)
    print(projected_logs)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b", "c"}


def test_loop_cut_0_binary():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case1", "case2", "case2", "case2"],
            "concept:name": ["a", "b", "a", "a", "c", "a"],
            "time:timestamp": [1, 2, 3, 1, 2, 3],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    dfg = DirectlyFollowsGraph(log).graph
    loop_cut = BinaryLoopCut(dfg)
    groups = loop_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b", "c"}
    projected_logs = loop_cut.project(log, groups)
    print(projected_logs)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b", "c"}


# ====== TESTS FOR SEQUENCE CUT ======


def test_sequence_cut_0():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case2", "case2", "case3", "case3"],
            "concept:name": ["a", "b", "a", "b", "a", "b"],
            "time:timestamp": [1, 2, 1, 2, 1, 2],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()

    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = SequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b"}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b"}


def test_sequence_cut_1():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case1", "case1"],
            "concept:name": ["a", "b", "c", "d"],
            "time:timestamp": [1, 2, 3, 4],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = SequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 4
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b"}
    assert set(groups[2]) == {"c"}
    assert set(groups[3]) == {"d"}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 4
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert (
            set(acts) == {"a"}
            or set(acts) == {"b"}
            or set(acts) == {"c"}
            or set(acts) == {"d"}
        )


def test_sequence_cut_1_binary():
    log = pd.DataFrame(
        {
            "case:concept:name": ["case1", "case1", "case1", "case1"],
            "concept:name": ["a", "b", "c", "d"],
            "time:timestamp": [1, 2, 3, 4],
        }
    )
    log = log.groupby("case:concept:name")["concept:name"].apply(list).tolist()
    dfg = DirectlyFollowsGraph(log).graph
    sequence_cut = BinarySequenceCut(dfg)
    groups = sequence_cut.discover()
    assert len(groups) == 2
    assert set(groups[0]) == {"a"}
    assert set(groups[1]) == {"b", "c", "d"}
    projected_logs = sequence_cut.project(log, groups)
    assert len(projected_logs) == 2
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b", "c", "d"}


def test_sequence_cut_with_empty_traces():
    from utils.directly_follows_graph import DirectlyFollowsGraph

    log = [["a", "b"], ["b", "c"]]

    dfg = DirectlyFollowsGraph(log).graph
    seq_cut = SequenceCut(dfg)
    groups = seq_cut.discover()
    projected_logs = seq_cut.project(log, groups)
    assert len(projected_logs) == 3
    for sublog in projected_logs:
        acts = {act for trace in sublog for act in trace}
        assert set(acts) == {"a"} or set(acts) == {"b"} or set(acts) == {"c"}

    for sublog in projected_logs:
        normalized = {tuple(trace) for trace in sublog}

        if any("a" in trace for trace in sublog):
            assert normalized == {("a",), ()}
        if any("b" in trace for trace in sublog):
            assert normalized == {("b",)}
            assert len(sublog) == 2
        if any("c" in trace for trace in sublog):
            assert normalized == {("c",), ()}
