import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4

from core.audit_config import AuditConfig
from core.logger import AuditLogger


class ExecutionDeadline:
    """Monotonic deadline tracker for audit executions using high-precision perf_counter."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        self.start_perf = time.perf_counter()
        self.deadline_perf = self.start_perf + timeout_seconds

    def remaining(self) -> float:
        """Returns remaining seconds until deadline expiration."""
        return max(0.0, self.deadline_perf - time.perf_counter())

    def expired(self) -> bool:
        """Returns True if the execution deadline has passed."""
        return time.perf_counter() >= self.deadline_perf


@dataclass
class ExecutionContext:
    """
    Unified execution context object encapsulating run identifiers, configuration,
    monotonic deadlines, operator cancellation tokens, and structured logging context.
    """
    run_id: str = field(default_factory=lambda: f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6]}")
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    parent_execution_id: Optional[str] = None
    config: Optional[AuditConfig] = None
    cancellation_token: threading.Event = field(default_factory=threading.Event)
    deadline: Optional[ExecutionDeadline] = None
    logger: Optional[AuditLogger] = None
    registry_snapshot_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.config and not self.deadline:
            timeout = getattr(self.config.execution, "timeout_seconds", 300)
            self.deadline = ExecutionDeadline(timeout)
        if self.config and not self.logger:
            self.logger = AuditLogger(
                name="AuditExecutionContext",
                framework_version=getattr(self.config.metadata, "framework_version", "1.0.0"),
                config_fingerprint=self.config.fingerprint()
            )
