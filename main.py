import networkx as nx
from typing import List
from cuts.exclusive import ExclusiveCut
if __name__ == "__main__":
    # Example DFG
    dfg = nx.DiGraph()
    dfg.add_edges_from([
        ('A', 'B'),
        ('B', 'C'),
        ('D', 'E'),
        ('E', 'F')
    ])
    
    exclusive_cut = ExclusiveCut(dfg)
    partitions = exclusive_cut.discover()
    print("Discovered Exclusive Partitions:")
    for partition in partitions:
        print(partition)
