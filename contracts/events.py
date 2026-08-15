from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone

@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    aggregate_id: str = ""
    event_type: str = "DOMAIN_EVENT"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict = field(default_factory=dict)
