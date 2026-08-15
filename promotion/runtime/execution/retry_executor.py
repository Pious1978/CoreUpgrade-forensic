import time
from typing import Any, Type
from .abstract import Executor
from ...domain.context import PromotionContext
from ...domain.result_types import PromotionResult
from ...governance.retry import RetryPolicy

class RetryExecutor(Executor):
    def __init__(self, inner: Executor) -> None:
        self.inner = inner

    def execute(self, source: Any, target_type: Type[Any], context: PromotionContext) -> PromotionResult:
        retry_count = 0
        max_retries = context.max_retries
        while retry_count <= max_retries:
            try:
                return self.inner.execute(source, target_type, context)
            except Exception as e:
                if RetryPolicy.evaluate(e) and retry_count < max_retries:
                    retry_count += 1
                    time.sleep(0.1 * (2 ** retry_count))
                    continue
                raise
