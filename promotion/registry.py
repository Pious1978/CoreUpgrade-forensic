from typing import Type, Dict, Tuple, Any
from .exceptions import RegistryFrozenError

class PromotionRegistry:
    """Internal class-keyed promotion registry supporting immutability locks."""
    
    def __init__(self) -> None:
        self._registry: Dict[Tuple[Type[Any], Type[Any]], Type[Any]] = {}
        self._frozen: bool = False

    def register(self, source_type: Type[Any], target_type: Type[Any], promoter_class: Type[Any]) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot register new promotion paths; PromotionRegistry is frozen.")
        key = (source_type, target_type)
        self._registry[key] = promoter_class

    def get(self, source_type: Type[Any], target_type: Type[Any]) -> Type[Any]:
        key = (source_type, target_type)
        if key not in self._registry:
            raise KeyError(f"No promotion path registered for contract classes '{source_type.__name__}' -> '{target_type.__name__}'.")
        return self._registry[key]

    def freeze(self) -> None:
        self._frozen = True

    def is_frozen(self) -> bool:
        return self._frozen

    def clear(self) -> None:
        self._frozen = False
        self._registry.clear()

# Global Singleton Instance (Internal/External entry point)
promotion_registry = PromotionRegistry()

def promotion(source: Type[Any], target: Type[Any]):
    """Decorator for automatic promoter class discovery and registration."""
    def decorator(cls):
        promotion_registry.register(source, target, cls)
        return cls
    return decorator
