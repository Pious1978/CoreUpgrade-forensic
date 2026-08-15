from typing import Any
from ..exceptions import CapabilityCheckError

class CapabilityGuard:
    """Enforces institutional permissions and execution scopes."""
    @staticmethod
    def require(source: Any, capability: str, context: Any) -> None:
        scopes = context.permissions.scopes
        if scopes and capability not in scopes:
            raise CapabilityCheckError(f"Context lacks required scope/capability: '{capability}'.")
