from abc import ABC, abstractmethod
from typing import Any, Optional
from .result_types import PromotionResult
from .idempotency_types import IdempotencyStatus

class AbstractIdempotencyStore(ABC):
    @abstractmethod
    def get_status(self, key: str) -> Optional[IdempotencyStatus]: pass
    @abstractmethod
    def set_status(self, key: str, status: IdempotencyStatus) -> None: pass
    @abstractmethod
    def transition_atomic(self, key: str, expected: IdempotencyStatus, new: IdempotencyStatus) -> bool: pass
    @abstractmethod
    def get_result(self, key: str) -> Optional[PromotionResult]: pass
    @abstractmethod
    def save_result(self, key: str, result: PromotionResult) -> None: pass

class PromotionLock(ABC):
    @abstractmethod
    def acquire(self, lock_key: str, lease_seconds: int = 30) -> Optional[str]: pass
    @abstractmethod
    def release(self, lock_key: str, token: str) -> bool: pass

class DeadLetterQueue(ABC):
    @abstractmethod
    def push(self, source_contract: Any, reason: str, metadata: Any) -> None: pass

class EventBus(ABC):
    @abstractmethod
    def publish(self, event: Any) -> None: pass

class MetricsCollector(ABC):
    @abstractmethod
    def record_latency(self, metric_name: str, duration_ms: float) -> None: pass
    @abstractmethod
    def record_counter(self, metric_name: str, value: int = 1) -> None: pass

class Tracer(ABC):
    @abstractmethod
    def trace_operation(self, operation_name: str) -> Any: pass

class Logger(ABC):
    @abstractmethod
    def info(self, message: str, context: dict) -> None: pass
    @abstractmethod
    def error(self, message: str, context: dict) -> None: pass

class AuditPublisher(ABC):
    @abstractmethod
    def publish(self, event_or_audit: Any) -> None: pass
