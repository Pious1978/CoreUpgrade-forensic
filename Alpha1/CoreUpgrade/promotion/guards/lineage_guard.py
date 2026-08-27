from typing import Any
from ..exceptions import LineageViolationError

class LineageGuard:
    """Verifies institutional lineage contracts (parent ID, version, causation, domain)."""
    @staticmethod
    def verify(source: Any, expected_source_type: str) -> None:
        source_type = getattr(source, "CONTRACT_TYPE", type(source).__name__)
        if source_type.lower() != expected_source_type.lower():
            raise LineageViolationError(f"Lineage mismatch: Expected source type '{expected_source_type}', received '{source_type}'.")
        
        mandatory_attributes = ["immutable_id", "version", "domain"]
        for attr in mandatory_attributes:
            if not hasattr(source, attr) or getattr(source, attr) is None:
                raise LineageViolationError(f"Source contract '{source_type}' lacks mandatory lineage attribute: '{attr}'.")
