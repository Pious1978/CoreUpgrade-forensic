import hashlib
from typing import List, Tuple, Any, Dict
from src.security.crypto import StrictCryptographicEngine

class DependencyResolver:
    @staticmethod
    def resolve_topological_sort(theorems: List[Any]) -> Tuple[List[Any], str]:
        theorem_map: Dict[str, Any] = {}
        for t in theorems:
            t_id = getattr(t, "id", None)
            if not t_id:
                raise ValueError(f"Theorem object {t} missing required 'id' attribute.")
            if t_id in theorem_map:
                raise ValueError(f"Duplicate theorem ID detected: {t_id}")
            theorem_map[t_id] = t

        for t_id, t in theorem_map.items():
            deps = getattr(t, "depends_on", [])
            for dep in deps:
                if dep not in theorem_map:
                    raise ValueError(f"Theorem '{t_id}' depends on missing theorem ID '{dep}'.")

        in_degree: Dict[str, int] = {t_id: 0 for t_id in theorem_map}
        adj_list: Dict[str, List[str]] = {t_id: [] for t_id in theorem_map}

        for t_id, t in theorem_map.items():
            for dep in getattr(t, "depends_on", []):
                adj_list[dep].append(t_id)
                in_degree[t_id] += 1

        queue = [t_id for t_id, deg in in_degree.items() if deg == 0]
        queue.sort()
        sorted_ids: List[str] = []

        while queue:
            curr = queue.pop(0)
            sorted_ids.append(curr)
            for neighbor in adj_list[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort()

        if len(sorted_ids) != len(theorem_map):
            raise RuntimeError("Circular dependency detected in theorem DAG execution graph.")

        sorted_theorems = [theorem_map[t_id] for t_id in sorted_ids]

        canonical_metadata = []
        for t in sorted_theorems:
            canonical_metadata.append({
                "id": getattr(t, "id"),
                "version": getattr(t, "version", "1.0"),
                "depends_on": sorted(list(getattr(t, "depends_on", [])))
            })

        dag_bytes = StrictCryptographicEngine.canonical_serialize(canonical_metadata)
        dag_hash = hashlib.sha256(dag_bytes).hexdigest()

        return sorted_theorems, dag_hash