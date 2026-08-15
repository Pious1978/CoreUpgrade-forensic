from abc import ABC, abstractmethod
from typing import Optional

class DistributedLock(ABC):
    """Clean distributed lock interface without redundant 'Abstract' prefix."""
    @abstractmethod
    def acquire(self, lock_key: str, lease_seconds: int = 30) -> Optional[str]: pass
    @abstractmethod
    def release(self, lock_key: str, token: str) -> bool: pass
