import networkx as nx
from typing import List
import pandas as pd

from cuts.base_cut import BaseCut

class LoopCut(BaseCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__("LoopCut", list(dfg.nodes), dfg)
        self.dfg = dfg

    def discover(self) -> List[set]:
        pass
    
    def project(self, traces : pd.DataFrame, groups: List[set]) -> pd.DataFrame:
        pass
