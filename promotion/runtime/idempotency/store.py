from abc import ABC, abstractmethod
from typing import Optional
from ...domain.result_types import PromotionResult
from .state_machine import IdempotencyStatus

class IdempotencyStore(ABC):
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
