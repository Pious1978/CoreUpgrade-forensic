import time
from typing import Any, Type
from .abstract import Executor
from ...domain.context import PromotionContext
from ...domain.result_types import PromotionResult
from ...exceptions import PromotionError

class CircuitBreakerExecutor(Executor):
    def __init__(self, inner: Executor, failure_threshold: int = 5, recovery_seconds: int = 30) -> None:
        self.inner = inner
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"

    def execute(self, source: Any, target_type: Type[Any], context: PromotionContext) -> PromotionResult:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self.recovery_seconds:
                self._state = "HALF-OPEN"
            else:
                raise PromotionError("Circuit breaker is OPEN. Fast-failing execution request.")

        try:
            result = self.inner.execute(source, target_type, context)
            if self._state == "HALF-OPEN":
                self._state = "CLOSED"
                self._failures = 0
            return result
        except Exception as e:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self.failure_threshold:
                self._state = "OPEN"
            raise
