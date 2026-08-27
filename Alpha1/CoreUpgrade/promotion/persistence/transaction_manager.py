from abc import ABC, abstractmethod

class AbstractTransactionManager(ABC):
    @abstractmethod
    def begin(self) -> None: pass
    @abstractmethod
    def commit(self) -> None: pass
    @abstractmethod
    def rollback(self) -> None: pass
