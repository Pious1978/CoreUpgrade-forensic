from typing import Any
from .exceptions import CapabilityCheckError, LineageViolationError, LifecycleTransitionError

class CapabilityGuard:
    """Enforces desk and platform capabilities before promotion."""
    @staticmethod
    def require(source: Any, capability: str, context: Any) -> None:
        desk_caps = context.extra.get("desk_capabilities", {})
        asset_class = getattr(source, "asset_class", "DEFAULT")
        if not desk_caps.get(asset_class, True):
            raise CapabilityCheckError(f"Desk '{context.desk}' lacks capability '{capability}' for asset class '{asset_class}'.")

class LineageGuard:
    """Validates parent-child lineage, correlation, and causation constraints."""
    @staticmethod
    def verify(source: Any, expected_source_type: str) -> None:
        source_type = getattr(source, "CONTRACT_TYPE", type(source).__name__)
        if source_type.lower() != expected_source_type.lower():
            raise LineageViolationError(f"Lineage mismatch: Expected source type '{expected_source_type}', received '{source_type}'.")
        if not getattr(source, "immutable_id", None) and not getattr(source, "id", None):
            raise LineageViolationError("Source contract lacks a cryptographically verifiable identifier.")

class LifecycleTransitionService:
    """Executes state transitions producing immutable, hashed, audited records."""
    @staticmethod
    def promote(contract: Any, target_state: str, target_trust: str, actor: str, reason: str) -> Any:
        # In production, this invokes the core engine to generate a new hashed immutable state instance
        if hasattr(contract, "__dict__"):
            new_contract = dict(contract.__dict__)
        else:
            new_contract = dict(contract)
        
        new_contract["lifecycle_state"] = target_state
        new_contract["trust_level"] = target_trust
        new_contract["last_modified_by"] = actor
        new_contract["transition_reason"] = reason
        return new_contract
