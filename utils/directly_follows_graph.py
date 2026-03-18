from typing import Dict, List, Tuple

import networkx as nx


class DirectlyFollowsGraph:
    def __init__(self, log: List[List[str]]):
        self.start_activities = set()
        self.end_activities = set()

        self.relations = self._extract_dfg_relations(log)
        self.graph = self._build_dfg()

    def _extract_dfg_relations(self, log: List) -> Dict[Tuple[str, str], int]:
        dfg_relations = dict()
        for trace in log:
            trace_start = trace[0] if trace else None
            trace_end = trace[-1] if trace else None

            if trace_start:
                # Add implicit edge (,trace_start) to represent start of trace
                dfg_relations[(None, trace_start)] = (
                    dfg_relations.get((None, trace_start), 0) + 1
                )
                self.start_activities.add(trace_start)
            if trace_end:
                # Add implicit edge (trace_end, implicit_end_node) to represent end of trace
                dfg_relations[(trace_end, None)] = (
                    dfg_relations.get((trace_end, None), 0) + 1
                )
                self.end_activities.add(trace_end)

            if not trace_start and not trace_end:
                # This is an empty trace, so we add an edge from start to end
                dfg_relations[(None, None)] = dfg_relations.get((None, None), 0) + 1
                self.start_activities.add(None)
                self.end_activities.add(None)

            for i in range(len(trace) - 1):
                a1 = trace[i]
                a2 = trace[i + 1]
                dfg_relations[(a1, a2)] = dfg_relations.get((a1, a2), 0) + 1
        return dfg_relations

    def get_start_activities(self):
        return self.start_activities

    def get_end_activities(self):
        return self.end_activities

    def _build_dfg(self) -> nx.DiGraph:
        dfg = nx.DiGraph()

        for (a1, a2), count in self.relations.items():
            if a1 is None and a2 is None:
                # This means we have an empty trace
                # add an artificial start and end node to represent this
                if "ArtificialNoneNode" not in dfg.nodes:
                    dfg.add_node("ArtificialNoneNode")
                dfg.add_edge("ArtificialNoneNode", "ArtificialNoneNode", weight=count)
            elif a1 is None:
                # add a2 if it isn't in the graph
                if a2 not in dfg.nodes:
                    dfg.add_node(a2)
                dfg.nodes[a2]["start"] = dfg.nodes[a2].get("start", 0) + count
            elif a2 is None:
                # add a1 if it isn't in the graph
                if a1 not in dfg.nodes:
                    dfg.add_node(a1)
                dfg.nodes[a1]["end"] = dfg.nodes[a1].get("end", 0) + count
            else:
                dfg.add_edge(a1, a2, weight=count)
        return dfg

    def visualize(self):
        import matplotlib.pyplot as plt

        # green for start act
        # red for end act
        # orange IF both start and end act
        # blue otherwise
        coloring = []
        for node in self.graph.nodes:
            if node in self.start_activities and node in self.end_activities:
                coloring.append("orange")
            elif node in self.start_activities:
                coloring.append("green")
            elif node in self.end_activities:
                coloring.append("red")
            else:
                coloring.append("blue")
        pos = nx.spring_layout(self.graph)
        nx.draw(self.graph, pos, with_labels=True, node_color=coloring)
        plt.show()
