from typing import Type, Set, List, Tuple, Any
from .exceptions import PromotionError

class GraphValidator:
    @staticmethod
    def find_cycles(nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> List[Tuple[Type[Any], Type[Any]]]:
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for src, tgt in edges:
                if src == node:
                    if tgt not in visited:
                        dfs(tgt)
                    elif tgt in rec_stack:
                        cycles.append((src, tgt))
            rec_stack.remove(node)

        for node in nodes:
            if node not in visited:
                dfs(node)
        return cycles

    @staticmethod
    def topological_sort(nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> List[Type[Any]]:
        in_degree = {node: 0 for node in nodes}
        adj = {node: [] for node in nodes}
        for src, tgt in edges:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        queue = [n for n, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            n = queue.pop(0)
            result.append(n)
            for neighbor in adj[n]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(nodes):
            raise PromotionError("Topological sort failed: Circular dependency detected.")
        return result

    @staticmethod
    def roots(nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> Set[Type[Any]]:
        targets = {tgt for _, tgt in edges}
        sources = {src for src, _ in edges}
        return sources - targets

    @staticmethod
    def leaves(nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> Set[Type[Any]]:
        sources = {src for src, _ in edges}
        return {node for node in nodes if node not in sources}

    @staticmethod
    def orphans(nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> Set[Type[Any]]:
        connected = {src for src, _ in edges}.union({tgt for _, tgt in edges})
        return nodes - connected

    @classmethod
    def validate(cls, nodes: Set[Type[Any]], edges: List[Tuple[Type[Any], Type[Any]]]) -> None:
        cycles = cls.find_cycles(nodes, edges)
        if cycles:
            raise PromotionError(f"Graph validation failed: Cycles detected -> {cycles}")
