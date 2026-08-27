import logging
import logging.handlers
import queue
import json
import socket
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum
import time


class AuditLogger:
    """Asynchronous, thread-safe structured enterprise logger utilizing QueueHandler/QueueListener."""

    _init_lock = threading.Lock()
    _queue = queue.Queue(-1)
    _listener = None

    def __init__(self, name: str = "AuditEngine", framework_version: str = "1.0.0", config_fingerprint: str = ""):
        self.logger = logging.getLogger(name)
        self.logger.propagate = False
        self.framework_version = framework_version
        self.config_fingerprint = config_fingerprint
        
        self.hostname = socket.gethostname()
        self.pid = os.getpid()

        with AuditLogger._init_lock:
            if not self.logger.handlers:
                stream_handler = logging.StreamHandler()
                stream_handler.setFormatter(logging.Formatter("%(message)s"))
                
                # Setup asynchronous QueueHandler & QueueListener
                q_handler = logging.handlers.QueueHandler(AuditLogger._queue)
                self.logger.addHandler(q_handler)
                self.logger.setLevel(logging.INFO)

                if AuditLogger._listener is None:
                    AuditLogger._listener = logging.handlers.QueueListener(
                        AuditLogger._queue, stream_handler, respect_handler_level=True
                    )
                    AuditLogger._listener.start()

        self._base_payload = {
            "hostname": self.hostname,
            "pid": self.pid,
            "process": os.getpid(),
            "framework_version": self.framework_version,
            "config_fingerprint": self.config_fingerprint,
        }

    def _normalize(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, dict):
            return {str(k): self._normalize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple, set)):
            return [self._normalize(x) for x in obj]
        return obj

    def event(self, event_name: str, audit_id: str, execution_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        payload = self._base_payload.copy()
        payload.update({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            "event": event_name,
            "audit_id": audit_id,
            "execution_id": execution_id,
            "thread": threading.current_thread().name,
        })
        if extra:
            payload.update(self._normalize(extra))
        self.logger.info(json.dumps(payload, default=str, separators=(",", ":")))
