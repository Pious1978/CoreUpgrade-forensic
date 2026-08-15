from typing import Dict, Set, List, Any
import hashlib
import json
from core.audit_registry import AuditRegistry


class RegistryValidationError(Exception):
    """Raised when framework registry validation fails due to architectural violations."""
    pass


class RegistryValidator:
    """
    Institutional validation engine that verifies registry integrity,
    metadata compliance, depth calculations, and reproducibility fingerprints.
    """

    VALID_CRITICALITIES = {"LOW", "NORMAL", "HIGH", "CRITICAL"}

    def __init__(self, registry: AuditRegistry):
        self.registry = registry

    def validate(self) -> None:
        """
        Executes all registry validation checks:
        1. Metadata integrity and policy constraints.
        2. Verifies that all declared dependencies exist in the registry.
        3. Detects circular dependencies using DFS cycle detection.
        """
        registered_ids = set(self.registry.list_audit_ids())
        metadata_map = {aid: self.registry.describe(aid) for aid in registered_ids}

        self._validate_metadata(metadata_map)
        self._validate_dependencies_exist(metadata_map, registered_ids)
        self._validate_no_cycles(metadata_map)

    def _validate_metadata(self, metadata_map: Dict[str, Any]) -> None:
        """Validates institutional execution policy constraints in metadata."""
        for audit_id, meta in metadata_map.items():
            if meta.criticality not in self.VALID_CRITICALITIES:
                raise RegistryValidationError(
                    f"Audit ID '{audit_id}' ({meta.name}) specifies invalid criticality '{meta.criticality}'. "
                    f"Must be one of {self.VALID_CRITICALITIES}."
                )
            if meta.estimated_runtime_seconds <= 0:
                raise RegistryValidationError(
                    f"Audit ID '{audit_id}' ({meta.name}) specifies invalid estimated runtime "
                    f"'{meta.estimated_runtime_seconds}s'. Must be greater than zero."
                )

    def _validate_dependencies_exist(self, metadata_map: Dict[str, Any], registered_ids: Set[str]) -> None:
        """Ensures every declared dependency is registered in the framework."""
        for audit_id, meta in metadata_map.items():
            for dep in meta.dependencies:
                if dep not in registered_ids:
                    raise RegistryValidationError(
                        f"Audit ID '{audit_id}' ({meta.name}) declares a dependency on unregistered audit ID '{dep}'."
                    )

    def _validate_no_cycles(self, metadata_map: Dict[str, Any]) -> None:
        """Detects circular dependencies in the audit DAG using a 3-state DFS algorithm."""
        WHITE, GRAY, BLACK = 0, 1, 2
        state: Dict[str, int] = {aid: WHITE for aid in metadata_map}

        def dfs(node: str, path: List[str]) -> None:
            state[node] = GRAY
            path.append(node)

            meta = metadata_map[node]
            for neighbor in meta.dependencies:
                if neighbor in state:
                    if state[neighbor] == GRAY:
                        cycle_path = " -> ".join(path[path.index(neighbor):] + [neighbor])
                        raise RegistryValidationError(
                            f"Circular dependency detected in audit registry DAG: {cycle_path}"
                        )
                    elif state[neighbor] == WHITE:
                        dfs(neighbor, path)

            path.pop()
            state[node] = BLACK

        for audit_id in metadata_map:
            if state[audit_id] == WHITE:
                dfs(audit_id, [])

    def calculate_depths(self) -> Dict[str, int]:
        """
        Calculates the dependency tree depth (layer index) for each audit module.
        Root audits with no dependencies have depth 0.
        """
        registered_ids = set(self.registry.list_audit_ids())
        metadata_map = {aid: self.registry.describe(aid) for aid in registered_ids}
        depths: Dict[str, int] = {}

        def get_depth(node: str, visited: Set[str]) -> int:
            if node in depths:
                return depths[node]
            if node in visited:
                return 0
            
            visited.add(node)
            meta = metadata_map.get(node)
            if not meta or not meta.dependencies:
                depths[node] = 0
            else:
                max_parent_depth = max(get_depth(dep, visited) for dep in meta.dependencies if dep in metadata_map)
                depths[node] = max_parent_depth + 1
            visited.remove(node)
            return depths[node]

        for audit_id in metadata_map:
            get_depth(audit_id, set())

        return depths

    def snapshot_fingerprint(self) -> str:
        """
        Generates a deterministic cryptographic hash fingerprint of the entire registry state 
        for reproducibility tracking across audit executions.
        """
        snapshot = self.registry.snapshot()
        canonical_payload = json.dumps(snapshot, sort_keys=True, default=str)
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:12]
