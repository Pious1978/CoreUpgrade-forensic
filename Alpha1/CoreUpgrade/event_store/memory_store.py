import threading
from typing import Dict, List, Optional, Tuple

from event_store.store_protocol import EventStore, StreamConcurrencyError
from oms.events.order_events import BaseOrderEvent


class InMemoryEventStore(EventStore):
    """Thread-safe, append-only memory store for executing and replaying event streams.
    
    Version Semantics:
    - Versions are 1-based event counts.
    - An empty stream is at version 0.
    - Appending 1 event to an empty stream results in stream version 1.
    
    Provides optimistic concurrency via `expected_version` to ensure webhooks or 
    concurrent engine threads do not silently overwrite interleaved facts.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._streams: Dict[str, List[BaseOrderEvent]] = {}

    def append_to_stream(
        self, 
        stream_id: str, 
        events: Tuple[BaseOrderEvent, ...], 
        expected_version: Optional[int] = None
    ) -> int:
        """Appends events to a stream. Raises if optimistic concurrency fails."""
        if not isinstance(stream_id, str) or not stream_id.strip():
            raise ValueError("stream_id must be a non-empty string")
        if not isinstance(events, tuple):
            raise TypeError(f"events must be a tuple, got {type(events)}")
        
        for event in events:
            if not isinstance(event, BaseOrderEvent):
                raise TypeError(f"All events must inherit from BaseOrderEvent, got {type(event)}")
                
        if expected_version is not None and not isinstance(expected_version, int):
            raise TypeError("expected_version must be an integer or None")

        with self._lock:
            current_stream = self._streams.get(stream_id, [])
            current_version = len(current_stream)
            
            # Concurrency Check
            if expected_version is not None and current_version != expected_version:
                raise StreamConcurrencyError(
                    f"Concurrency conflict on stream '{stream_id}'. "
                    f"Expected version {expected_version}, actual version {current_version}."
                )
            
            # Extend and reassign (immutable to callers since they pass tuples, 
            # but we store internally as a list for easy extension)
            current_stream.extend(events)
            self._streams[stream_id] = current_stream
            
            return len(current_stream)

    def read_stream(self, stream_id: str) -> Tuple[BaseOrderEvent, ...]:
        """Returns an immutable tuple of the stream's current history.
        Events are strictly ordered by append sequence.
        """
        if not isinstance(stream_id, str) or not stream_id.strip():
            raise ValueError("stream_id must be a non-empty string")
            
        with self._lock:
            return tuple(self._streams.get(stream_id, []))
