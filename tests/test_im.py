"""
def traces_to_df(traces):
        rows = []
        prev_timestamp = 0
        for i, trace in enumerate(traces, start=1):
            case_id = f"c{i}"
            for act in trace:
                rows.append({
                    "case:concept:name": case_id,
                    "concept:name": act,
                    "time:timestamp" : prev_timestamp + 1
                })
                prev_timestamp += 1
        return pd.DataFrame(rows)
    log_2 = traces_to_df([
        ["a", "b", "c"],
        ["a", "c", "b"],
        ["d", "e"],
        ["d", "f"],
        ["a", "b", "c"],
        ["a", "c", "b"],
        ["d", "e"],
        ["d", "f"],
    ])
    # they should be exactly the same
    result_tree_2 = apply_binary_IM(log_2)
    result_tree_2_im = inductive_miner.apply(log_2)
    print(pm4py.behavioral_similarity(result_tree_2, result_tree_2_im))
    # a flower model log 
    # find all possible permutations of 
    # THIS ONE IS WRONG, check once again the cut and the projection

    log_diff = traces_to_df([
     ['a', 'b'],
     ['b', 'c'],
     ['c', 'a'],
    ])
    result_tree_diff = apply_binary_IM(log_diff)
    result_tree_diff_im = inductive_miner.apply(log_diff)
    print("Behavioral similarity between Binary IM and IM on the flower model log: ")
    print(result_tree_diff)
    print(result_tree_diff_im)
    print(pm4py.behavioral_similarity(result_tree_diff, result_tree_diff_im))
"""