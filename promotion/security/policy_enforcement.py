from typing import Any
from .authorization import AuthorizationService
from ..exceptions import CapabilityCheckError

class PolicyEnforcement:
    @staticmethod
    def enforce(identity: Any, required_scope: str) -> None:
        if not AuthorizationService.check_permission(identity, required_scope):
            raise CapabilityCheckError(f"Security Policy Enforcement failed for identity: {identity.actor}")
