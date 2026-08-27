from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Universal transport wrapper for routing and tracing events across the Event Bus."""
    
    event_id: str
    stream_id: str
    stream_version: int
    event_type: str
    
    # Distributed Tracing
    correlation_id: str  # The ID of the original request (e.g., intent_id) spanning the whole saga
    causation_id: str    # The ID of the specific command/event that directly triggered this one
    
    persisted_at: datetime
    
    # The raw, cryptographically verified JSON payload (from SerializedEvent)
    payload: str
