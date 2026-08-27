import threading
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from .events import PromotionDomainEvent, PromotionTrace
from .serializers.event_serializer import EventSerializer
from .events.event_envelope import EventEnvelope
from .exceptions import OptimisticLockFailure

@dataclass(frozen=True)
class StoredEvent:
    event_id: UUID
    stream_id: UUID
    sequence: int
    envelope: EventEnvelope
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID

class EventStore:
    """Thread-safe event store supporting optimistic concurrency checks and schema versioning."""
    def __init__(self) -> None:
        self._streams: Dict[UUID, List[StoredEvent]] = {}
        self._lock = threading.RLock()

    def append(
        self,
        stream_id: UUID,
        event: PromotionDomainEvent,
        event_version: int = 1,
        expected_sequence: Optional[int] = None,
        correlation_id: UUID = None,
        causation_id: UUID = None
    ) -> StoredEvent:
        with self._lock:
            if stream_id not in self._streams:
                self._streams[stream_id] = []
            stream = self._streams[stream_id]
            current_seq = len(stream)
            
            if expected_sequence is not None and current_seq != expected_sequence:
                raise OptimisticLockFailure(f"Optimistic concurrency violation: Expected sequence {expected_sequence}, but stream is at {current_seq}.")

            seq = current_seq + 1
            serialized_payload = EventSerializer.serialize(event)
            envelope = EventEnvelope(
                event_type=type(event).__name__,
                version=event_version,
                payload=serialized_payload
            )
            stored = StoredEvent(
                event_id=uuid4(),
                stream_id=stream_id,
                sequence=seq,
                envelope=envelope,
                occurred_at=datetime.now(timezone.utc),
                correlation_id=correlation_id or event.trace_id,
                causation_id=causation_id or event.trace_id
            )
            stream.append(stored)
            return stored

    def get_stream(self, stream_id: UUID) -> Tuple[StoredEvent, ...]:
        with self._lock:
            return tuple(self._streams.get(stream_id, []))

    def reconstruct_trace(self, stream_id: UUID) -> PromotionTrace:
        stored_events = self.get_stream(stream_id)
        domain_events = tuple(
            PromotionDomainEvent(
                event_name=se.envelope.event_type,
                idempotency_key=se.envelope.payload.get("idempotency_key", ""),
                trace_id=se.correlation_id,
                timestamp=se.occurred_at.timestamp()
            )
            for se in stored_events
        )
        return PromotionTrace.from_events(domain_events)
