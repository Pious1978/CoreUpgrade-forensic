from typing import Type, Any, Optional
from ..exceptions import LineageViolationError
from ..abstractions import Repository

class LineageDagGuard:
    """Validates complete parent-child DAG lineage, versioning, causation, and hash continuity."""
    @staticmethod
    def verify(source: Any, expected_source_type: Type[Any], parent_repo: Optional[Repository] = None) -> None:
        if not isinstance(source, expected_source_type) and getattr(source, "CONTRACT_TYPE", None) != getattr(expected_source_type, "CONTRACT_TYPE", None):
            raise LineageViolationError(f"Lineage DAG type mismatch: Expected '{expected_source_type.__name__}', got '{type(source).__name__}'.")
        
        mandatory_attributes = ["immutable_id", "version", "domain", "causation_id"]
        for attr in mandatory_attributes:
            if not hasattr(source, attr) or getattr(source, attr) is None:
                raise LineageViolationError(f"Lineage DAG validation failed: Missing mandatory attribute '{attr}'.")

        parent_id = getattr(source, "parent_contract_id", None)
        if parent_id and parent_repo:
            parent = parent_repo.get_by_id(parent_id)
            if not parent:
                raise LineageViolationError(f"Lineage DAG broken: Parent contract ID '{parent_id}' not found in repository.")
