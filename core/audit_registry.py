from typing import Dict, Type, List, Tuple, Any
from core.audit_base import BaseAudit
from core.audit_metadata import AuditMetadata


class AuditRegistry:
    """
    Institutional registry for automatic discovery, registration, 
    dependency indexing, category indexing, and versioned snapshots of audit modules.
    """

    def __init__(self):
        self._registry: Dict[str, Type[BaseAudit]] = {}
        self._metadata_index: Dict[str, AuditMetadata] = {}
        self._dependency_index: Dict[str, Tuple[str, ...]] = {}
        self._category_index: Dict[str, List[Type[BaseAudit]]] = {}

    def register(self, audit_class: Type[BaseAudit]) -> Type[BaseAudit]:
        """
        Registers an audit class into the registry, indexing metadata, 
        pre-computing dependency maps, grouping by category, and verifying version collisions.
        """
        metadata = getattr(audit_class, "METADATA", None)
        if not metadata or not isinstance(metadata, AuditMetadata):
            raise ValueError(
                f"Audit class '{audit_class.__name__}' must define a class-level 'METADATA' attribute of type AuditMetadata."
            )
        
        audit_id = metadata.audit_id
        if audit_id in self._registry:
            existing_class = self._registry[audit_id]
            existing_meta = getattr(existing_class, "METADATA", None)
            existing_version = existing_meta.version if existing_meta else "unknown"
            
            if existing_version == metadata.version:
                raise ValueError(
                    f"Audit ID '{audit_id}' version '{metadata.version}' is already registered by '{existing_class.__name__}'."
                )
            else:
                raise ValueError(
                    f"Version conflict for Audit ID '{audit_id}': existing is version '{existing_version}' "
                    f"({existing_class.__name__}), attempting to register version '{metadata.version}' ({audit_class.__name__})."
                )

        self._registry[audit_id] = audit_class
        self._metadata_index[audit_id] = metadata
        self._dependency_index[audit_id] = metadata.dependencies

        cat = metadata.category.lower()
        if cat not in self._category_index:
            self._category_index[cat] = []
        self._category_index[cat].append(audit_class)

        return audit_class

    def unregister(self, audit_id: str) -> None:
        """Removes an audit from all internal indices."""
        if audit_id in self._registry:
            audit_class = self._registry.pop(audit_id)
            metadata = self._metadata_index.pop(audit_id, None)
            self._dependency_index.pop(audit_id, None)
            if metadata:
                cat = metadata.category.lower()
                if cat in self._category_index:
                    self._category_index[cat] = [c for c in self._category_index[cat] if c != audit_class]

    def get(self, audit_id: str) -> Type[BaseAudit]:
        """Retrieves an audit class by its unique programmatic ID."""
        if audit_id not in self._registry:
            raise KeyError(f"Audit with ID '{audit_id}' is not registered in the framework.")
        return self._registry[audit_id]

    def describe(self, audit_id: str) -> AuditMetadata:
        """Inspects audit metadata without instantiating the class."""
        if audit_id not in self._metadata_index:
            raise KeyError(f"Audit with ID '{audit_id}' is not registered.")
        return self._metadata_index[audit_id]

    def get_dependencies(self, audit_id: str) -> Tuple[str, ...]:
        """Returns static dependencies for an audit ID instantly from the dependency index."""
        if audit_id not in self._dependency_index:
            raise KeyError(f"Audit with ID '{audit_id}' is not registered.")
        return self._dependency_index[audit_id]

    def get_by_category(self, category: str) -> List[Type[BaseAudit]]:
        """Returns all audit classes belonging to a specific category."""
        return self._category_index.get(category.lower(), [])

    def list_audit_ids(self) -> List[str]:
        """Returns a list of all registered audit IDs."""
        return list(self._registry.keys())

    def get_all_classes(self) -> List[Type[BaseAudit]]:
        """Returns all registered audit classes."""
        return list(self._registry.values())

    def snapshot(self) -> Dict[str, Any]:
        """Generates a structured run manifest snapshot of all registered audits for traceability."""
        return {
            "registered_count": len(self._registry),
            "audits": [
                {
                    "audit_id": meta.audit_id,
                    "name": meta.name,
                    "category": meta.category,
                    "version": meta.version,
                    "tags": list(meta.tags),
                    "dependencies": list(meta.dependencies),
                    "class_name": self._registry[aid].__name__
                }
                for aid, meta in sorted(self._metadata_index.items())
            ]
        }

    def clear(self) -> None:
        """Clears all registrations and indices (useful for testing)."""
        self._registry.clear()
        self._metadata_index.clear()
        self._dependency_index.clear()
        self._category_index.clear()


# Global framework registry instance for convenient plugin imports
global_audit_registry = AuditRegistry()
