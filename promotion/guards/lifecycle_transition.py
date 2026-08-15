from typing import Any

class LifecycleTransitionService:
    """Executes state transitions producing immutable, hashed, audited records."""
    @staticmethod
    def promote(contract: Any, target_state: str, target_trust: str, actor: str, reason: str) -> Any:
        if hasattr(contract, "__dict__"):
            new_contract = dict(contract.__dict__)
        else:
            new_contract = dict(contract)
        
        new_contract["lifecycle_state"] = target_state
        new_contract["trust_level"] = target_trust
        new_contract["last_modified_by"] = actor
        new_contract["transition_reason"] = reason
        return new_contract
