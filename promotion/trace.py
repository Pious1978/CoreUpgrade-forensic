from dataclasses import dataclass, field
from typing import Any, Dict, Tuple
from uuid import UUID
import time

@dataclass(frozen=True)
class PromotionDomainEvent:
    """Immutable event record enabling full event-sourced timeline reconstruction."""
    event_name: str
    idempotency_key: str
    trace_id: UUID
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PromotionTrace:
    """Reconstructed execution timeline built entirely from emitted domain events."""
    events: Tuple[PromotionDomainEvent, ...] = ()

    @classmethod
    def from_events(cls, events: Tuple[PromotionDomainEvent, ...]) -> "PromotionTrace":
        return cls(events=events)
