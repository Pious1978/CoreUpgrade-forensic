"""
Dependency Resolver & Graph Hash Engine

Authority:
    Execution Layer Dependency Graph Validation & Fingerprinting
"""
import hashlib
import json
from typing import Tuple, Type, List
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

class DependencyResolver:
    @staticmethod
    def resolve_topological_sort(available_classes: List[Type[EmpiricalTheorem]]) -> Tuple[Tuple[Type[EmpiricalTheorem], ...], str]:
        validated_map = {}
        seen_ids = set()

        for theorem in available_classes:
            t_id = getattr(theorem, "id", None)
            if not t_id:
                raise RuntimeError(f"Theorem class missing unique ID.")
            if t_id in seen_ids:
                raise RuntimeError(f"Duplicate theorem ID: '{t_id}'.")
            seen_ids.add(t_id)
            validated_map[t_id] = theorem

        sorted_theorems: List[Type[EmpiricalTheorem]] = []
        visited = set()
        temp_marked = set()

        def visit(t_id: str):
            if t_id in temp_marked:
                raise RuntimeError(f"Circular dependency detected involving theorem '{t_id}'.")
            if t_id not in visited:
                temp_marked.add(t_id)
                theorem_cls = validated_map[t_id]
                deps = sorted(list(getattr(theorem_cls, "depends_on", ())))
                for dep_id in deps:
                    if dep_id not in validated_map:
                        raise KeyError(f"Theorem '{t_id}' depends on unregistered dependency '{dep_id}'.")
                    visit(dep_id)
                temp_marked.remove(t_id)
                visited.add(t_id)
                sorted_theorems.append(theorem_cls)

        for t_id in sorted(validated_map.keys()):
            if t_id not in visited:
                visit(t_id)

        dag_structure = {
            t.id: sorted(list(getattr(t, "depends_on", ())))
            for t in sorted_theorems
        }
        dag_bytes = json.dumps(dag_structure, sort_keys=True).encode("utf-8")
        dag_hash = hashlib.sha256(dag_bytes).hexdigest()

        return tuple(sorted_theorems), dag_hash
```[cite: 34]