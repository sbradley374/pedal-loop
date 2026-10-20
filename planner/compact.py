"""Lossless directed chain compression: search junctions, export original edges."""
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
import heapq
import math
import threading


@dataclass(eq=False)
class Arc:
    edges: tuple

    @property
    def u(self):
        return self.edges[0].u

    @property
    def v(self):
        return self.edges[-1].v


class Compact:
    def __init__(self, graph):
        self.adj = defaultdict(list)
        self.interior = defaultdict(list)
        incoming = defaultdict(list)
        for edges in graph.adj.values():
            for edge in edges:
                incoming[edge.v].append(edge)
        # Keep junctions, dead ends, restrictions, and topology transitions.
        anchors = {n for n in graph.nodes if len(graph.neighbors[n]) != 2}
        anchors.update(graph.restriction_nodes)
        for n in graph.nodes:
            if n in anchors:
                continue
            for previous in incoming[n]:
                onward = [e for e in graph.adj[n] if e.v != previous.u]
                if len(onward) != 1:
                    anchors.add(n)
                    break
        visited = set()

        def follow(first):
            chain = [first]
            visited.add(id(first))
            edge = first
            while edge.v not in anchors:
                onward = [e for e in graph.adj[edge.v] if e.v != edge.u]
                if len(onward) != 1 or id(onward[0]) in visited:
                    break
                edge = onward[0]
                visited.add(id(edge))
                chain.append(edge)
            arc = Arc(tuple(chain))
            self.adj[arc.u].append(arc)
            for i, part in enumerate(chain[1:], 1):
                self.interior[part.u].append((arc, i))

        for n in anchors:
            for edge in graph.adj[n]:
                if id(edge) not in visited:
                    follow(edge)
        # Isolated rings have no junction. Pick a natural break without deleting it.
        for edges in graph.adj.values():
            for edge in edges:
                if id(edge) not in visited:
                    follow(edge)
        self.arc_count = sum(map(len, self.adj.values()))
        self.landmark_nodes = []
        self.prepared = OrderedDict()
        self.prepare_lock = threading.Lock()
        neighbors = defaultdict(set)
        for node, arcs in self.adj.items():
            for arc in arcs:
                neighbors[node].add(arc.v)
                neighbors[arc.v].add(node)
        # Select landmarks in the largest weakly connected component.
        unseen = set(neighbors)
        largest = set()
        while unseen:
            component, stack = set(), [unseen.pop()]
            while stack:
                node = stack.pop()
                component.add(node)
                for other in neighbors[node]:
                    if other in unseen:
                        unseen.remove(other)
                        stack.append(other)
            if len(component) > len(largest):
                largest = component
        if largest:
            chosen = set()
            for lat_sign, lon_sign in ((1,1), (1,-1), (-1,1), (-1,-1)):
                chosen.add(max(largest, key=lambda n: (
                    lat_sign*graph.nodes[n][0]+lon_sign*graph.nodes[n][1], n)))
            self.landmark_nodes = sorted(chosen)

    @staticmethod
    def _distances(adjacency, start):
        best, queue = {start:0}, [(0,start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != best[node]: continue
            for end, length in adjacency.get(node, ()):
                new = cost+length
                if new < best.get(end, math.inf):
                    best[end] = new
                    heapq.heappush(queue,(new,end))
        return best

    def prepare(self, graph, prefs, cost_function):
        key=tuple(prefs.get(k) for k in ('traffic','stops','hills','strict','avoid_major'))
        with self.prepare_lock:
            if key in self.prepared:
                self.prepared.move_to_end(key)
                return self.prepared[key]
            forward, reverse = defaultdict(list), defaultdict(list)
            base = {}
            for node, arcs in self.adj.items():
                for arc in arcs:
                    weight=sum(cost_function(graph,e,prefs) for e in arc.edges)
                    base[arc]=weight
                    if math.isfinite(weight):
                        forward[node].append((arc.v,weight))
                        reverse[arc.v].append((node,weight))
            # Ignore turn restrictions and repeated-edge penalties, retaining an
            # admissible lower bound for the actual preference-weighted search.
            landmarks=[(self._distances(forward,n),self._distances(reverse,n)) for n in self.landmark_nodes]
            self.prepared[key]=(base,landmarks)
            while len(self.prepared)>2:self.prepared.popitem(last=False)
            return base,landmarks

    def lower_bound(self, goal, prepared, graph, prefs, cost_function):
        targets = []
        for forward, reverse in prepared[1]:
            to_goal, from_goal = forward.get(goal,math.inf), reverse.get(goal,math.inf)
            for arc,index in self.interior.get(goal,()):
                prefix = sum(cost_function(graph,e,prefs) for e in arc.edges[:index])
                suffix = sum(cost_function(graph,e,prefs) for e in arc.edges[index:])
                to_goal = min(to_goal,forward.get(arc.u,math.inf)+prefix)
                from_goal = min(from_goal,reverse.get(arc.v,math.inf)+suffix)
            targets.append((forward,reverse,to_goal,from_goal))

        def estimate(node):
            bound = 0
            for forward,reverse,to_goal,from_goal in targets:
                if math.isfinite(to_goal) and node in forward:
                    bound = max(bound,to_goal-forward[node])
                if math.isfinite(from_goal) and node in reverse:
                    bound = max(bound,reverse[node]-from_goal)
            return bound
        return estimate

    def for_search(self, start, goal):
        """Split only arcs containing the two search endpoints."""
        overrides = {}
        for arc, index in self.interior.get(goal, ()):
            overrides[arc] = Arc(arc.edges[:index])
        initial = []
        for arc, index in self.interior.get(start, ()):
            end = len(overrides[arc].edges) if arc in overrides else len(arc.edges)
            if index < end:
                initial.append(Arc(arc.edges[index:end]))
            else:
                initial.append(Arc(arc.edges[index:]))

        def outgoing(node):
            arcs = [overrides.get(arc, arc) for arc in self.adj.get(node, ())]
            if node == start:
                arcs.extend(initial)
            return arcs

        return outgoing


_build_lock = threading.Lock()


def get_compact(graph):
    # Graphs are immutable once published to request workers.
    with _build_lock:
        if graph.compact is None:
            graph.compact = Compact(graph)
    return graph.compact
