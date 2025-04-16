import heapq
import math

class DStarLite:
    def __init__(self, graph, heuristic):
        self.graph = graph
        self.heuristic = heuristic
        self.km = 0
        self.rhs = {}
        self.g = {}
        self.U = []
        self.s_last = None

    def initialize(self, start, goal):
        self.start = start
        self.goal = goal
        self.rhs = {node: float('inf') for node in self.graph.nodes()}
        self.g = {node: float('inf') for node in self.graph.nodes()}

        self.rhs[goal] = 0
        self.s_last = start

        self.U = []
        self.push_queue(goal, self.calculate_key(goal))

    def calculate_key(self, s):
        return (
            min(self.g[s], self.rhs[s]) + self.heuristic(self.start, s) + self.km,
            min(self.g[s], self.rhs[s])
        )

    def push_queue(self, s, key):
        heapq.heappush(self.U, (key, s))

    def update_vertex(self, u):
        if u != self.goal:
            self.rhs[u] = min([
                self.g.get(s, float('inf')) + self.graph[u][s]['weight']
                for s in self.graph.successors(u)
            ] or [float('inf')])

        in_queue = [i for k, i in self.U]
        if u in in_queue:
            self.U = [(k, s) for k, s in self.U if s != u]
            heapq.heapify(self.U)

        if self.g[u] != self.rhs[u]:
            self.push_queue(u, self.calculate_key(u))

    def compute_shortest_path(self):
        while self.U:
            k_old, u = heapq.heappop(self.U)
            k_new = self.calculate_key(u)

            if k_old < k_new:
                self.push_queue(u, k_new)
            elif self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for s in self.graph.predecessors(u):
                    self.update_vertex(s)
            else:
                self.g[u] = float('inf')
                self.update_vertex(u)
                for s in self.graph.predecessors(u):
                    self.update_vertex(s)

    def replan(self, start, goal):
        self.initialize(start, goal)
        self.compute_shortest_path()
        return self.extract_path()

    def extract_path(self):
        path = [self.start]
        current = self.start

        while current != self.goal:
            if not list(self.graph.successors(current)):
                return None
            min_cost = float('inf')
            next_node = None
            for s in self.graph.successors(current):
                cost = self.graph[current][s]['weight'] + self.g.get(s, float('inf'))
                if cost < min_cost:
                    min_cost = cost
                    next_node = s

            if next_node is None:
                return None
            path.append(next_node)
            current = next_node

        return path
