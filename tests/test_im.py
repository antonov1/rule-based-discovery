import pm4py
from inductive_miner.main import apply_IM
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.simulation.playout.process_tree.algorithm import (
    apply as playout_process_tree,
)
from pm4py.algo.simulation.tree_generator.algorithm import (
    apply as simulate_process_tree,
)
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.conversion.log.variants.df_to_event_log_1v import (
    apply as df_to_event_log,
)


def preprocess_log_v2(log):
    idx = 0
    time = 0
    for trace in log:
        for event in trace:
            event["case:concept:name"] = f"case_{idx}"
            event["time_timestamp"] = time
            time += 1
        idx += 1
    return log


def test_im():
    for i in range(10):
        process_tree = simulate_process_tree()
        log = preprocess_log_v2(playout_process_tree(process_tree))
        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

        model_sim = apply_IM(log)
        model_pm4py = inductive_miner.apply(df_to_event_log(log))
        sim = pm4py.behavioral_similarity(model_sim, model_pm4py)
        assert sim == 1.0, f"Similarity is {sim} for test {i}"
