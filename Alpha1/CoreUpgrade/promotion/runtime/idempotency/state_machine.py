from enum import Enum
from typing import Dict, List
from ...exceptions import IdempotencyTransitionError

class IdempotencyStatus(Enum):
    RECEIVED = "RECEIVED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"

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
