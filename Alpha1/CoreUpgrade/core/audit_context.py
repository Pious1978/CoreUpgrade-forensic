import logging
import threading
from typing import Any, Dict, List
from core.audit_result import AuditResult
from core.telemetry import TelemetryCollector

class AuditContext:
    """Thread-safe controlled API providing shared state, caching, and telemetry."""

    def __init__(self):
        self._results: List[AuditResult] = []
        self._state: Dict[str, Any] = {}
        self._cache_store: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}
        self.telemetry = TelemetryCollector()
        self._logger = logging.getLogger("AuditContext")
        self._lock = threading.Lock()

    def add_result(self, result: AuditResult) -> None:
        with self._lock:
            self._results.append(result)

    def get_results(self) -> List[AuditResult]:
        with self._lock:
            return list(self._results)

    def get_database(self) -> Any:
        with self._lock:
            return self._state.get("database_client")

    def get_market_data(self) -> Any:
        with self._lock:
            return self._state.get("market_data_provider")

    def record_metric(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[f"metric_{key}"] = value

    def cache(self, key: str, value: Any = None) -> Any:
        with self._lock:
            if value is not None:
                self._cache_store[key] = value
            return self._cache_store.get(key)

    def logger(self) -> logging.Logger:
        return self._logger

    def state(self, key: str, value: Any = None) -> Any:
        with self._lock:
            if value is not None:
                self._state[key] = value
            return self._state.get(key)

    def record_error(self, module_name: str, error_msg: str) -> None:
        with self._lock:
            self._errors[module_name] = error_msg
