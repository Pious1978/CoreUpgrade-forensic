from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
import time

@dataclass(frozen=True)
class PromotionContext:
    """Comprehensive execution metadata for tracing, lineage, and idempotency."""
    actor: str
    desk: str
    strategy: str
    approval_level: str
    dry_run: bool = False
    promotion_id: UUID = field(default_factory=uuid4)
    workflow_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = field(default_factory=uuid4)
    causation_id: Optional[UUID] = None
    request_timestamp: float = field(default_factory=time.time)
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = "DEFAULT"
    environment: str = "PRODUCTION"
    trace_id: UUID = field(default_factory=uuid4)
    extra: Dict[str, Any] = field(default_factory=dict)
