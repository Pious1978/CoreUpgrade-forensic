import time
import threading
from typing import Any, Optional

class CacheManager:
    """Thread-safe centralized cache implementation with TTL support."""

    def __init__(self):
        self._store: dict = {}
        self._expiry: dict = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        with self._lock:
            self._store[key] = value
            if ttl_seconds:
                self._expiry[key] = time.time() + ttl_seconds
            elif key in self._expiry:
                del self._expiry[key]

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
            return self._store.get(key)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._expiry.clear()

cache_manager = CacheManager()
