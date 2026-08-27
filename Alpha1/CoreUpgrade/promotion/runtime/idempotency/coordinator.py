from typing import Optional
from .store import IdempotencyStore
from .state_machine import IdempotencyStatus
from ...domain.result_types import PromotionResult
from ...exceptions import PromotionError

class IdempotencyCoordinator:
    def __init__(self, store: IdempotencyStore) -> None:
        self.store = store

    def check_or_acquire(self, key: str) -> Optional[PromotionResult]:
        status = self.store.get_status(key)
        if status == IdempotencyStatus.COMPLETED:
            return self.store.get_result(key)
        if status == IdempotencyStatus.RUNNING:
            raise PromotionError(f"Promotion already running for idempotency key: {key}")

        acquired = self.store.transition_atomic(key, status or IdempotencyStatus.RECEIVED, IdempotencyStatus.RUNNING)
        if not acquired:
            raise PromotionError(f"Concurrent promotion race detected for idempotency key: {key}")
        return None
