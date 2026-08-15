from dataclasses import dataclass, field, replace
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
import time
import socket
import os

@dataclass(frozen=True)
class PromotionMetadata:
    """Immutable diagnostic metadata hiding runtime performance tracking from JSON serializers."""
    promotion_id: UUID = field(default_factory=uuid4)
    started_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at_utc: Optional[datetime] = None
    _perf_start: float = field(default_factory=time.perf_counter, repr=False, compare=False)
    duration_ms: float = 0.0
    policy_name: str = "DEFAULT"
    policy_version: str = "1.0.0"
    engine_version: str = "2.7.0"
    actor: str = "SYSTEM"
    trigger: str = "MANUAL"
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))
    retry_count: int = 0
    host: str = field(default_factory=socket.gethostname)
    node: str = field(default_factory=lambda: os.getenv("KUBERNETES_NODE_NAME", "local-node"))
    worker: str = field(default_factory=lambda: os.getenv("WORKER_ID", f"pid-{os.getpid()}"))

    def finalize(self) -> "PromotionMetadata":
        duration = (time.perf_counter() - self._perf_start) * 1000.0
        return replace(
            self,
            completed_at_utc=datetime.now(timezone.utc),
            duration_ms=duration
        )
