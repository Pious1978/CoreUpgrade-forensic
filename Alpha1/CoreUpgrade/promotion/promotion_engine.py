from typing import Any, Type
from .promotion_context import PromotionContext
from .promotion_result import PromotionResult
from .promotion_registry import promotion_registry

class PromotionEngine:
    """Façade providing a clean API for executing promotions via contract-class registry lookup."""

    @classmethod
    def promote(cls, source_contract: Any, target_contract: Type, context: PromotionContext) -> PromotionResult:
        source_type = type(source_contract)
        promoter_class = promotion_registry.get(source_type, target_contract)
        promoter_instance = promoter_class()
        return promoter_instance.promote(source_contract, context)
