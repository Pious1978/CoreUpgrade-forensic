from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BaseOrderEvent:
    """Immutable base fact for all order lifecycle events."""
    event_id: str
    intent_id: str
    execution_trace_id: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id cannot be empty")
        if not self.intent_id.strip():
            raise ValueError("intent_id cannot be empty")
        if not self.execution_trace_id.strip():
            raise ValueError("execution_trace_id cannot be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
