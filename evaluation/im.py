"""
if __name__ == "__main__":

    import pm4py
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

    times_BIM = []
    times_sIM = []
    times_pm4py = []
    events = 0
    cases = 0
    similarity_to_pm4py_bim = []
    similarity_to_pm4py_sim = []

    for i in range(200):
        process_tree = simulate_process_tree()
        log = preprocess_log_v2(playout_process_tree(process_tree))
        log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

        print(
            f"Log has {len(log)} events and {len(log['concept:name'].unique())} unique activities."
        )
        # apply the binary IM
        events += len(log)
        cases += len(log["case:concept:name"].unique())
        # BIM
        start_time = pd.Timestamp.now()
        model_bim = apply_IM(log)
        end_time = pd.Timestamp.now()
        times_BIM.append((end_time - start_time).total_seconds() * 1000)
        # SIM
        start_time = pd.Timestamp.now()
        model_sim = apply_IM(log)
        end_time = pd.Timestamp.now()
        times_sIM.append((end_time - start_time).total_seconds() * 1000)
        start_time = pd.Timestamp.now()
        model_pm4py = inductive_miner.apply(df_to_event_log(log))
        end_time = pd.Timestamp.now()
        times_pm4py.append((end_time - start_time).total_seconds() * 1000)
        sim_pm4py_sim = pm4py.behavioral_similarity(model_sim, model_pm4py)
        print(f"MODEL SIM: {model_sim}")
        print(f"MODEL PM4Py: {model_pm4py}")
        print(sim_pm4py_sim)

        similarity_to_pm4py_bim.append(
            pm4py.behavioral_similarity(model_bim, model_pm4py)
        )
        similarity_to_pm4py_sim.append(sim_pm4py_sim)

    # A histogram on runtimes (two boxplots)
    import matplotlib.pyplot as plt

    plt.boxplot(
        [times_BIM, times_sIM, times_pm4py],
        labels=["Binary IM", "Standard IM", "PM4Py IM"],
    )
    plt.ylabel("Runtime (ms)")
    plt.title("Runtime Comparison of Binary IM, Standard IM, and PM4Py IM")
    # a subtitle for avg trace len
    avg_trace_len = events / cases if cases > 0 else 0
    plt.suptitle(f"Average Trace Length: {avg_trace_len:.2f}", fontsize=10)
    plt.show()

    def ecdf(data):
        x = np.sort(data)
        y = np.arange(1, len(x) + 1) / len(x)
        return x, y

    x_bim, y_bim = ecdf(similarity_to_pm4py_bim)
    x_sim, y_sim = ecdf(similarity_to_pm4py_sim)

    plt.plot(x_bim, y_bim, label="BIM")
    plt.plot(x_sim, y_sim, label="SIM")

    plt.xlabel("Behavioral Similarity (comp w/ PM4Py's version)")
    plt.ylabel("Cumulative Probability")
    plt.title("ECDF of Similarity Scores")
    plt.legend()
    plt.grid(True)
    plt.show()
    import pm4py


log = pm4py.read_xes("./binary_im/BPIC2017.xes")
    # to a dataframe
    log = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)
    print(
        f"BPIC2012 log has {len(log)} events and {len(log['concept:name'].unique())} unique activities."
    )
    start_time = pd.Timestamp.now()
    model_bim = apply_IM(log)
    end_time = pd.Timestamp.now()
    print(f"IM took {(end_time - start_time).total_seconds()} seconds on BPIC2012 log.")
    start_time = pd.Timestamp.now()
    model_pm4py = inductive_miner.apply(df_to_event_log(log))
    end_time = pd.Timestamp.now()
    print(
        f"PM4Py IM took {(end_time - start_time).total_seconds()} seconds on BPIC2012 log."
    )
    # display model_bim
    gviz = pt_visualizer.apply(model_bim)
    pt_visualizer.view(gviz)
    print(
        f"Similarity between Binary IM and PM4Py IM on BPIC2012 log: {pm4py.behavioral_similarity(model_bim, model_pm4py)}"
    )

    print(f"Process tree discovered by Binary IM on BPIC2012 log: {model_bim}")
    print(f"Process tree discovered by PM4Py IM on BPIC2012 log: {model_pm4py}")
    print(f"Similarity is {pm4py.behavioral_similarity(model_bim, model_pm4py)}")


    log1 = [
        ['W_Call incomplete files', 'A_Incomplete', 'O_Create Offer', 'O_Created'],
        ['W_Call incomplete files', 'A_Incomplete', 'O_Accepted', 'A_Pending'],
        ['W_Call incomplete files', 'O_Accepted', 'A_Pending'],
        ['W_Call incomplete files', 'A_Incomplete', 'A_Denied', 'O_Refused'],
        ['O_Returned', 'O_Accepted', 'A_Pending'],
        ['O_Returned'],
        ['W_Shortened completion '],
        ['O_Create Offer', 'O_Created'],
    ]


    model_my_miner = apply_IM(log1)
    model_pm4py = inductive_miner.apply(df_to_event_log(log1))
    print(f"Model PM4Py: {model_pm4py}")
    print(f"SIM: {model_my_miner}")
    print(f"Sim: {pm4py.behavioral_similarity(model_my_miner, model_pm4py)}")
    # Print


"""
