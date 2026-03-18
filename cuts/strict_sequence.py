import sys
from typing import List, Set

import networkx as nx
from cuts.sequence import SequenceCut


class StrictSequenceCut(SequenceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "StrictSequenceCut"

    @staticmethod
    def _construct_alphabet_cluster_map(groups: List[Set[str]]):
        cmap = {}
        for i, g in enumerate(groups):
            for a in g:
                cmap[a] = i
        return cmap

    @staticmethod
    def _skippable(
        p: int, dfg: nx.DiGraph, start: Set[str], end: Set[str], groups: List[Set[str]]
    ) -> bool:
        # edge jumps over p
        for i in range(0, p):
            for j in range(p + 1, len(groups)):
                for a in groups[i]:
                    for b in groups[j]:
                        if dfg.has_edge(a, b):
                            return True

        # some later group can start directly
        for i in range(p + 1, len(groups)):
            for a in groups[i]:
                if a in start:
                    return True

        # some earlier group can end directly
        for i in range(0, p):
            for a in groups[i]:
                if a in end:
                    return True

        return False

    def discover(self) -> List[Set[str]]:
        c = super().discover()
        if c is None:
            return None

        start = {n for n in self.dfg.nodes if self.dfg.nodes[n].get("start", 0) > 0}
        end = {n for n in self.dfg.nodes if self.dfg.nodes[n].get("end", 0) > 0}

        mf = [
            (-sys.maxsize if len(G.intersection(start)) > 0 else sys.maxsize) for G in c
        ]
        mt = [
            (sys.maxsize if len(G.intersection(end)) > 0 else -sys.maxsize) for G in c
        ]

        cmap = self._construct_alphabet_cluster_map(c)

        for a, b in self.dfg.edges:
            mt[cmap[a]] = max(mt[cmap[a]], cmap[b])
            mf[cmap[b]] = min(mf[cmap[b]], cmap[a])

        for p in range(len(c)):
            if self._skippable(p, self.dfg, start, end, c):
                q = p - 1
                while q >= 0 and mt[q] <= p:
                    c[p] |= c[q]
                    c[q] = set()
                    q -= 1

                q = p + 1
                while q < len(mf) and mf[q] >= p:
                    c[p] |= c[q]
                    c[q] = set()
                    q += 1

        c = [g for g in c if len(g) > 0]
        return c if len(c) > 1 else None


class BinaryStrictSequenceCut(StrictSequenceCut):
    def __init__(self, dfg: nx.DiGraph) -> None:
        super().__init__(dfg)
        self.name = "BinaryStrictSequenceCut"
        self.dfg = dfg

    def discover(self) -> List[Set[str]]:
        groups = super().discover()
        if groups is None or len(groups) <= 2:
            return groups

        # keep the first group, merge the rest
        merged_rest = set().union(*groups[1:])
        return [groups[0], merged_rest]
