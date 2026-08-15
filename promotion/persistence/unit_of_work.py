from abc import ABC, abstractmethod
from typing import Tuple, Any

class AbstractUnitOfWork(ABC):
    @abstractmethod
    def stage_contract(self, contract: Any) -> None: pass
    @abstractmethod
    def stage_event(self, event: Any) -> None: pass
    @abstractmethod
    def stage_audit(self, audit: Any) -> None: pass
    @abstractmethod
    def stage_metric(self, metric: Any) -> None: pass
    @abstractmethod
    def commit(self) -> Tuple[Any, ...]: pass
    @abstractmethod
    def rollback(self) -> None: pass
