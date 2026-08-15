from typing import Dict, List, Tuple, Protocol, Any
from dataclasses import dataclass, field

@dataclass(frozen=True)
class StoredEvent:
    stream_id: str
    sequence_number: int
    event_type: str
    payload: Any
    timestamp: int

class EventStore(Protocol):
    def append(self, stream_id: str, event_type: str, payload: Any, timestamp: int) -> int:
        ...
    def get_stream(self, stream_id: str) -> Tuple[StoredEvent, ...]:
        ...

class InMemoryEventStore:
    def __init__(self):
        self._streams: Dict[str, List[StoredEvent]] = {}

    def append(self, stream_id: str, event_type: str, payload: Any, timestamp: int) -> int:
        if stream_id not in self._streams:
            self._streams[stream_id] = []
        
        stream = self._streams[stream_id]
        seq = len(stream) + 1
        stored = StoredEvent(
            stream_id=stream_id,
            sequence_number=seq,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp
        )
        stream.append(stored)
        return seq

    def get_stream(self, stream_id: str) -> Tuple[StoredEvent, ...]:
        return tuple(self._streams.get(stream_id, []))
