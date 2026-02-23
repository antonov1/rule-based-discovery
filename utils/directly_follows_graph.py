import networkx as nx
from typing import List, Tuple, Dict

class DirectlyFollowsGraph:
    def __init__(self, log : List):
        self.log = log
        self.dfg = self._build_dfg()
    
    def _build_dfg(self) -> nx.DiGraph:
        dfg = nx.DiGraph()
        for trace in self.log:
            for i in range(len(trace) - 1):
                a1 = trace[i]
                a2 = trace[i + 1]
                if dfg.has_edge(a1, a2):
                    dfg[a1][a2]['weight'] += 1
                else:
                    dfg.add_edge(a1, a2, weight=1)
        return dfg
    
    def __get_start_activities(self) -> List[str]:
        return [node for node in self.dfg.nodes if self.dfg.in_degree(node) == 0]
    
    def __get_end_activities(self) -> List[str]:
        return [node for node in self.dfg.nodes if self.dfg.out_degree(node) == 0]
    
    def __repr__(self) -> str:
        return "DirectlyFollowsGraph with {} nodes and {} edges".format(
            self.dfg.number_of_nodes(), self.dfg.number_of_edges()
        )