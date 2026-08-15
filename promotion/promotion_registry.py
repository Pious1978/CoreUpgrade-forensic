from typing import Type, Dict, Tuple
from .base_promoter import BasePromotionService
from .exceptions import RegistryFrozenError

class PromotionRegistry:
    """Global registry mapping (SourceContractClass, TargetContractClass) with immutability locking."""
    
    def __init__(self) -> None:
        self._registry: Dict[Tuple[str, str], Type[BasePromotionService]] = {}
        self._frozen: bool = False

    def register(self, source_contract_type: Type, target_contract_type: Type, promoter_class: Type[BasePromotionService]) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot register new promotion paths; PromotionRegistry is frozen.")
        
        src_name = getattr(source_contract_type, "CONTRACT_TYPE", source_contract_type.__name__)
        tgt_name = getattr(target_contract_type, "CONTRACT_TYPE", target_contract_type.__name__)
        key = (src_name.lower(), tgt_name.lower())
        self._registry[key] = promoter_class

    def get(self, source_contract_type: Any, target_contract_type: Any) -> Type[BasePromotionService]:
        src_name = getattr(source_contract_type, "CONTRACT_TYPE", source_contract_type if isinstance(source_contract_type, str) else source_contract_type.__name__)
        tgt_name = getattr(target_contract_type, "CONTRACT_TYPE", target_contract_type if isinstance(target_contract_type, str) else target_contract_type.__name__)
        key = (src_name.lower(), tgt_name.lower())
        
        if key not in self._registry:
            raise KeyError(f"No promotion path registered for contract classes '{src_name}' -> '{tgt_name}'.")
        return self._registry[key]

    def freeze(self) -> None:
        self._frozen = True

    def is_frozen(self) -> bool:
        return self._frozen

    def clear(self) -> None:
        self._frozen = False
        self._registry.clear()

# Global Singleton Instance
promotion_registry = PromotionRegistry()
