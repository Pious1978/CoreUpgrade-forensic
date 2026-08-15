from dataclasses import dataclass, field
from typing import Any, Dict
from uuid import UUID, uuid4
from datetime import datetime, timezone

@dataclass(frozen=True)
class EventEnvelope:
    """Comprehensive institutional event envelope containing complete causal tracing metadata."""
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID = field(default_factory=uuid4)
    payload: Dict[str, Any] = field(default_factory=dict)
