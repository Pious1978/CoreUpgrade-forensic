from typing import Optional, Protocol, Tuple

from oms.events.order_events import BaseOrderEvent


class StreamConcurrencyError(Exception):
    """Raised when the expected stream version does not match the actual version,
    preventing race conditions during event appends.
    """
    pass


class EventStore(Protocol):
    """Protocol for an append-only immutable event store."""

    def append_to_stream(
        self, 
        stream_id: str, 
        events: Tuple[BaseOrderEvent, ...], 
        expected_version: Optional[int] = None
    ) -> int:
        """Appends a sequence of events to a specific stream.
        
        Args:
            stream_id: The unique identifier for the event stream (e.g., intent_id).
            events: An ordered tuple of immutable events.
            expected_version: For optimistic concurrency. If provided, the append
                              must fail if the stream's current version does not match.
                              
        Returns:
            The new version integer of the stream.
            
        Raises:
            StreamConcurrencyError: If expected_version does not match reality.
        """
        ...

    def read_stream(self, stream_id: str) -> Tuple[BaseOrderEvent, ...]:
        """Retrieves the full, ordered history of events for a given stream."""
        ...
