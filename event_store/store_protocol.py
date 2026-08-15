from typing import Optional, Protocol, Tuple

from event_store.exceptions import StreamConcurrencyError
from oms.events.order_events import BaseOrderEvent


class EventStore(Protocol):
    """Protocol for an append-only immutable event store."""

    def append_to_stream(
        self,
        stream_id: str,
        events: Tuple[BaseOrderEvent, ...],
        expected_version: Optional[int] = None,
    ) -> int:
        ...

    def read_stream(
        self,
        stream_id: str,
    ) -> Tuple[BaseOrderEvent, ...]:
        ...