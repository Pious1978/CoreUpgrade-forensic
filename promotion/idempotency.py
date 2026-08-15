import threading
from typing import Optional, Dict, List
from .result_types import PromotionResult
from .exceptions import IdempotencyTransitionError
from .idempotency_types import IdempotencyStatus
from .abstractions import AbstractIdempotencyStore

_ALLOWED_TRANSITIONS: Dict[IdempotencyStatus, List[IdempotencyStatus]] = {
    IdempotencyStatus.RECEIVED: [IdempotencyStatus.RUNNING],
    IdempotencyStatus.RUNNING: [IdempotencyStatus.COMPLETED, IdempotencyStatus.FAILED_RETRYABLE, IdempotencyStatus.FAILED_FINAL],
    IdempotencyStatus.FAILED_RETRYABLE: [IdempotencyStatus.RUNNING],
    IdempotencyStatus.COMPLETED: [],
    IdempotencyStatus.FAILED_FINAL: []
}

def validate_idempotency_transition(old: IdempotencyStatus, new: IdempotencyStatus) -> None:
    if new not in _ALLOWED_TRANSITIONS.get(old, []):
        raise IdempotencyTransitionError(f"Invalid idempotency state transition from '{old.value}' to '{new.value}'.")

class InMemoryIdempotencyStore(AbstractIdempotencyStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._statuses: Dict[str, IdempotencyStatus] = {}
        self._results: Dict[str, PromotionResult] = {}

    def get_status(self, key: str) -> Optional[IdempotencyStatus]:
        with self._lock:
            return self._statuses.get(key)

    def set_status(self, key: str, status: IdempotencyStatus) -> None:
        with self._lock:
            old = self._statuses.get(key, IdempotencyStatus.RECEIVED)
            validate_idempotency_transition(old, status)
            self._statuses[key] = status

    def transition_atomic(self, key: str, expected: IdempotencyStatus, new: IdempotencyStatus) -> bool:
        with self._lock:
            current = self._statuses.get(key, IdempotencyStatus.RECEIVED)
            if current != expected:
                return False
            validate_idempotency_transition(current, new)
            self._statuses[key] = new
            return True

    def get_result(self, key: str) -> Optional[PromotionResult]:
        with self._lock:
            return self._results.get(key)

    def save_result(self, key: str, result: PromotionResult) -> None:
        with self._lock:
            current = self._statuses.get(key, IdempotencyStatus.RECEIVED)
            if current != IdempotencyStatus.RUNNING:
                raise IdempotencyTransitionError(f"Cannot save result: Idempotency status must be 'RUNNING', currently '{current.value}'.")
            validate_idempotency_transition(current, IdempotencyStatus.COMPLETED)
            self._results[key] = result
            self._statuses[key] = IdempotencyStatus.COMPLETED
