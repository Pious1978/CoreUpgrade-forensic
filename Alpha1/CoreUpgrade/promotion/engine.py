from typing import Callable, Any, Type
from .context import PromotionContext
from .result import PromotionResult

class PromotionEngine:
    """100% stateless pure coordinator delegating execution entirely to injected executors or pipelines."""
    def __init__(self, executor: Callable[[Any, Type[Any], PromotionContext], PromotionResult]) -> None:
        self._executor = executor

    def promote(self, source_contract: Any, target_contract_type: Type[Any], context: PromotionContext) -> PromotionResult:
        return self._executor(source_contract, target_contract_type, context)
