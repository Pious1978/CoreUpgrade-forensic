import time
from typing import Callable, Any, Type
from .abstract import AbstractPromotionExecutor
from ..context import PromotionContext
from ..result_types import PromotionResult
from ..retry import RetryPolicy
from ..exceptions import PromotionError

class RetryExecutor(AbstractPromotionExecutor):
    """Execution runtime wrapping inner promotion logic with exponential backoff retry policies."""
    def __init__(self, inner_executor: Callable[[Any, Type[Any], PromotionContext], PromotionResult]) -> None:
        self.inner_executor = inner_executor

    def execute(self, source: Any, target_type: Type[Any], context: PromotionContext) -> PromotionResult:
        retry_count = 0
        max_retries = context.max_retries

        while retry_count <= max_retries:
            try:
                return self.inner_executor(source, target_type, context)
            except Exception as e:
                if RetryPolicy.evaluate(e) and retry_count < max_retries:
                    retry_count += 1
                    time.sleep(0.1 * (2 ** retry_count))
                    continue
                else:
                    raise PromotionError(f"Promotion failed permanently after {retry_count} retries: {e}") from e
