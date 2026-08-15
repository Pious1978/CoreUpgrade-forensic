from typing import Any, Type
from ..domain.context import PromotionContext
from ..domain.result_types import PromotionResult
from ..runtime.execution.abstract import Executor

class PromotionEngine:
    """100% pure stateless coordinator delegating all orchestration to the execution pipeline."""
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def promote(self, source_contract: Any, target_contract_type: Type[Any], context: PromotionContext) -> PromotionResult:
        return self.executor.execute(source_contract, target_contract_type, context)
