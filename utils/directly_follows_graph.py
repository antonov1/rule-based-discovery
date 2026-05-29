import heapq
import math
from collections import deque
from typing import Dict, List, Tuple

import networkx as nx


class DirectlyFollowsGraph:
    # Artificial start and end nodes used only for filtering purposes, not actually added to the graph
    start = "__START__"
    end = "__END__"

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

    def visualize_filtered(self, filtered_dfg: nx.DiGraph):
        import matplotlib.pyplot as plt

        coloring = []
        for node in filtered_dfg.nodes:
            if node in self.start_activities and node in self.end_activities:
                coloring.append("orange")
            elif node in self.start_activities:
                coloring.append("green")
            elif node in self.end_activities:
                coloring.append("red")
            else:
                coloring.append("blue")
        pos = nx.spring_layout(filtered_dfg)
        nx.draw(filtered_dfg, pos, with_labels=True, node_color=coloring)
        plt.show()

    @staticmethod
    def _bfs_reachable(starts, graph: nx.DiGraph):
        q = deque(starts)
        seen = set(starts)

        while q:
            u = q.popleft()

            for v in graph.successors(u):
                if v not in seen:
                    seen.add(v)
                    q.append(v)

        return seen

    @staticmethod
    def _reverse_bfs_next_multi_sink(sinks, graph: nx.DiGraph):
        """
        next_hop[x] = y means x -> y moves closer to one of the sinks.
        """
        q = deque(sinks)
        next_hop = {sink: None for sink in sinks}

        while q:
            v = q.popleft()

            for u in graph.predecessors(v):
                if u not in next_hop:
                    next_hop[u] = v
                    q.append(u)

        return next_hop

    @staticmethod
    def _widest_parents_multi_source(sources, graph: nx.DiGraph):
        """
        Multi-source widest path.
        parent[v] = u means u -> v is the selected previous edge.
        """
        width = {s: math.inf for s in sources}
        parent = {s: None for s in sources}

        heap = [(-width[s], s) for s in sources]
        heapq.heapify(heap)

        while heap:
            neg_w, u = heapq.heappop(heap)
            w_u = -neg_w

            if w_u != width.get(u):
                continue

            for v in graph.successors(u):
                edge_weight = graph[u][v].get("weight", 1)
                cap = min(w_u, edge_weight)

                if cap > width.get(v, -1):
                    width[v] = cap
                    parent[v] = u
                    heapq.heappush(heap, (-cap, v))

        return parent

    @staticmethod
    def _reverse_widest_next_multi_sink(sinks, graph: nx.DiGraph):
        """
        Reverse widest path.
        next_hop[u] = v means u -> v is the selected next edge toward a sink.
        """
        width = {sink: math.inf for sink in sinks}
        next_hop = {sink: None for sink in sinks}

        heap = [(-width[sink], sink) for sink in sinks]
        heapq.heapify(heap)

        while heap:
            neg_w, v = heapq.heappop(heap)
            w_v = -neg_w

            if w_v != width.get(v):
                continue

            for u in graph.predecessors(v):
                edge_weight = graph[u][v].get("weight", 1)
                cap = min(w_v, edge_weight)

                if cap > width.get(u, -1):
                    width[u] = cap
                    next_hop[u] = v
                    heapq.heappush(heap, (-cap, u))

        return next_hop

    @staticmethod
    def _to_augmented_graph(dfg: nx.DiGraph) -> nx.DiGraph:
        rebuilt = nx.DiGraph()
        start = DirectlyFollowsGraph.start
        end = DirectlyFollowsGraph.end

        rebuilt.add_node(start)
        rebuilt.add_node(end)

        # Add activities
        for node, data in dfg.nodes(data=True):
            if node == "ArtificialNoneNode":
                continue
            rebuilt.add_node(node)
            start_count = data.get("start", 0)
            end_count = data.get("end", 0)

            if start_count > 0:
                rebuilt.add_edge(start, node, weight=start_count)

            if end_count > 0:
                rebuilt.add_edge(node, end, weight=end_count)

        # Add directly-follows relations
        for a1, a2, data in dfg.edges(data=True):
            weight = data.get("weight", 1)

            if a1 == a2 and a1 == "ArtificialNoneNode":
                # Empty trace.
                rebuilt.add_edge(start, end, weight=weight)
                continue

            if a1 == "ArtificialNoneNode" or a2 == "ArtificialNoneNode":
                continue

            rebuilt.add_edge(a1, a2, weight=weight)

        return rebuilt

    @staticmethod
    def _add_edge_with_max_weight(graph: nx.DiGraph, u, v, weight):
        if graph.has_edge(u, v):
            graph[u][v]["weight"] = max(graph[u][v].get("weight", 0), weight)
        else:
            graph.add_edge(u, v, weight=weight)

    @staticmethod
    def _from_augmented_graph(augmented: nx.DiGraph) -> nx.DiGraph:
        dfg = nx.DiGraph()

        start = DirectlyFollowsGraph.start
        end = DirectlyFollowsGraph.end

        for node in augmented.nodes:
            if node not in {start, end}:
                dfg.add_node(node)

        for u, v, data in augmented.edges(data=True):
            weight = data.get("weight", 1)

            if u == start and v == end:
                node = "ArtificialNoneNode"
                dfg.add_node(node)
                dfg.add_edge(node, node, weight=weight)
                continue

            if u == start:
                if v not in dfg:
                    dfg.add_node(v)

                dfg.nodes[v]["start"] = max(
                    dfg.nodes[v].get("start", 0),
                    weight,
                )

                continue

            if v == end:
                if u not in dfg:
                    dfg.add_node(u)

                dfg.nodes[u]["end"] = max(
                    dfg.nodes[u].get("end", 0),
                    weight,
                )

                continue

            dfg.add_edge(u, v, weight=weight)

        return dfg

    @staticmethod
    def filter(threshold: float, dfg: nx.DiGraph) -> nx.DiGraph:
        """
        Filters a DFG using Split-Miner-style relative edge filtering,
        then repairs the graph so every original activity remains on some
        START -> ... -> END path.

        Input:
            dfg: nx.DiGraph of the DFG.

        Output:
            Filtered DFG in your normal representation.
        """
        if not 0 <= threshold <= 1:
            raise ValueError("Threshold must be between 0 and 1")

        start = DirectlyFollowsGraph.start
        end = DirectlyFollowsGraph.end

        original = DirectlyFollowsGraph._to_augmented_graph(dfg)

        if start not in original:
            raise ValueError("Augmented graph has no start node")

        if end not in original:
            raise ValueError("Augmented graph has no end node")

        activities = {node for node in original.nodes if node not in {start, end}}

        # ------------------------------------------------------------
        # 1. Check original START -> END connectivity assumption
        # ------------------------------------------------------------

        reachable_from_start = DirectlyFollowsGraph._bfs_reachable(
            {start},
            original,
        )

        next_to_end = DirectlyFollowsGraph._reverse_bfs_next_multi_sink(
            {end},
            original,
        )

        on_path = {
            a for a in activities if a in reachable_from_start and a in next_to_end
        }

        if on_path != activities:
            missing = activities - on_path
            raise ValueError(
                f"Assumption violated: Not all activities are on path from START to END : {missing}"
            )

        # ------------------------------------------------------------
        # 2. Noise filtering
        # ------------------------------------------------------------

        outgoing_max_occ = {}

        for u, v, data in original.edges(data=True):
            weight = data.get("weight", 1)
            outgoing_max_occ[u] = max(outgoing_max_occ.get(u, 0), weight)

        filtered = nx.DiGraph()

        # Add all nodes and their attributes
        filtered.add_nodes_from(original.nodes(data=True))

        for u, v, data in original.edges(data=True):
            weight = data.get("weight", 1)
            max_out = outgoing_max_occ.get(u, weight)

            if weight >= threshold * max_out:
                filtered.add_edge(u, v, weight=weight)

        # ------------------------------------------------------------
        # 3. Ensure at least one start edge and one end edge survived
        # ------------------------------------------------------------

        if filtered.out_degree(start) == 0:
            best_start_edge = max(
                original.out_edges(start, data=True),
                key=lambda edge: edge[2].get("weight", 1),
            )

            u, v, data = best_start_edge
            filtered.add_edge(u, v, weight=data.get("weight", 1))

        if filtered.in_degree(end) == 0:
            best_end_edge = max(
                original.in_edges(end, data=True),
                key=lambda edge: edge[2].get("weight", 1),
            )

            u, v, data = best_end_edge
            filtered.add_edge(u, v, weight=data.get("weight", 1))

        # ------------------------------------------------------------
        # 4. Repair
        # ------------------------------------------------------------

        while True:
            reachable = DirectlyFollowsGraph._bfs_reachable(
                {start},
                filtered,
            )

            next_to_end = DirectlyFollowsGraph._reverse_bfs_next_multi_sink(
                {end},
                filtered,
            )

            backbone = {a for a in activities if a in reachable and a in next_to_end}

            broken = activities - backbone

            if not broken:
                break

            co_reachable = set(next_to_end.keys())

            parent_from_reachable_in_original = (
                DirectlyFollowsGraph._widest_parents_multi_source(
                    reachable,
                    original,
                )
            )

            next_to_coreachable_in_original = (
                DirectlyFollowsGraph._reverse_widest_next_multi_sink(
                    co_reachable,
                    original,
                )
            )

            progressed = False

            for activity in broken:
                # ----------------------------------------------------
                # 4a. Add path from current reachable area to activity
                # ----------------------------------------------------

                if activity not in parent_from_reachable_in_original:
                    raise ValueError(
                        f"Repair failed: cannot reach {activity} from current "
                        f"reachable set in original graph."
                    )

                path_nodes = []
                x = activity

                while x is not None and x not in reachable:
                    path_nodes.append(x)
                    x = parent_from_reachable_in_original[x]

                for node in reversed(path_nodes):
                    u = parent_from_reachable_in_original[node]
                    v = node

                    if u is None:
                        continue

                    weight = original[u][v].get("weight", 1)

                    DirectlyFollowsGraph._add_edge_with_max_weight(
                        filtered,
                        u,
                        v,
                        weight,
                    )

                    progressed = True

                # ----------------------------------------------------
                # 4b. Add path from activity to current co-reachable area
                # ----------------------------------------------------

                if activity not in next_to_coreachable_in_original:
                    raise ValueError(
                        f"Repair failed: cannot connect {activity} to END from "
                        f"current co-reachable set in original graph."
                    )

                x = activity

                while x is not None and x not in co_reachable:
                    y = next_to_coreachable_in_original[x]

                    if y is None:
                        break

                    weight = original[x][y].get("weight", 1)

                    DirectlyFollowsGraph._add_edge_with_max_weight(
                        filtered,
                        x,
                        y,
                        weight,
                    )

                    progressed = True
                    x = y

            if not progressed:
                raise ValueError(
                    "Repair made no progress; this should be impossible under "
                    "the original connectivity assumption."
                )

        return DirectlyFollowsGraph._from_augmented_graph(filtered)
