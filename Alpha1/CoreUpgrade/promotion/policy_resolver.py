from typing import Type, Dict, Tuple, Any
from .policies.base_policy import BasePromotionPolicy
from .exceptions import PolicyResolutionError

class PolicyResolver:
    """Resolves promotion policies dynamically based on transition, tenant, context, or time."""

    def __init__(self) -> None:
        self._policies: Dict[Tuple[Type[Any], Type[Any]], Type[BasePromotionPolicy]] = {}

    def register(self, source_type: Type[Any], target_type: Type[Any], policy_class: Type[BasePromotionPolicy]) -> None:
        self._policies[(source_type, target_type)] = policy_class

    def resolve(self, source_type: Type[Any], target_type: Type[Any], context: Any) -> BasePromotionPolicy:
        key = (source_type, target_type)
        if key not in self._policies:
            raise PolicyResolutionError(f"No policy resolved for transition '{source_type.__name__}' -> '{target_type.__name__}'.")
        return self._policies[key]()
