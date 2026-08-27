# execution/events/event_store.py
import dataclasses
from typing import List, Sequence
from datetime import datetime
from execution.contracts.execution_event import ExecutionEvent

@dataclasses.dataclass(frozen=True)
class StoredEvent:
    sequence_id: int
    event: ExecutionEvent
    stored_timestamp: datetime

class EventStore:
    """
    Append-only, immutable event log for execution event sourcing.
    Enforces chronological ordering, duplicate-event prevention, 
    and complete state reproducibility via deterministic replay.
    """
    def __init__(self):
        self._store: List[StoredEvent] = []
        self._seen_event_ids: set[str] = set()

    def append(self, event: ExecutionEvent, timestamp: datetime) -> StoredEvent:
        """Appends a canonical ExecutionEvent to the store in strict chronological sequence."""
        if event.event_id in self._seen_event_ids:
            raise ValueError(
                f"EventStore violation: Event ID '{event.event_id}' has already been appended. "
                "Duplicate ingestion is strictly prohibited."
            )

        sequence_id = len(self._store) + 1
        stored = StoredEvent(
            sequence_id=sequence_id,
            event=event,
            stored_timestamp=timestamp
        )
        
        self._store.append(stored)
        self._seen_event_ids.add(event.event_id)
        return stored

    def get_events_for_order(self, order_id: str) -> Sequence[ExecutionEvent]:
        """Retrieves all chronological execution events associated with a specific order identifier."""
        return [se.event for se in self._store if se.event.order_id == order_id]

    def get_all_events(self) -> Sequence[ExecutionEvent]:
        """Retrieves the complete global chronological event stream for system-wide replay."""
        return [se.event for se in self._store]

    @property
    def total_events(self) -> int:
        return len(self._store)