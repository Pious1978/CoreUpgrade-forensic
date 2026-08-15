import threading
from typing import Dict
from uuid import uuid4
from .abstractions import PromotionLock

class InMemoryPromotionLock(PromotionLock):
    """Thread-safe in-memory distributed lock enforcing ownership token validation on release."""
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leases: Dict[str, str] = {}

    def acquire(self, lock_key: str, lease_seconds: int = 30) -> Optional[str]:
        with self._lock:
            if lock_key in self._leases:
                return None
            token = str(uuid4())
            self._leases[lock_key] = token
            return token

    def release(self, lock_key: str, token: str) -> bool:
        with self._lock:
            if self._leases.get(lock_key) == token:
                del self._leases[lock_key]
                return True
            return False
