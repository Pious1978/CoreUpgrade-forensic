from typing import Any, Dict, List, Optional, Tuple

from event_store.exceptions import (
    EventStoreError,
    OutOfOrderEventError,
    StreamConcurrencyError,
)


class ImmutableEventStore:
    """
    In-memory append-only event store.

    Public reads return immutable tuples.
    Streams use optimistic concurrency via expected_version.
    """

    def __init__(self) -> None:
        self._events: List[Any] = []
        self._streams: Dict[str, List[Any]] = {}

    def append(self, event: Any) -> None:
        """
        Legacy/global append API.

        Kept for compatibility with older callers.
        """
        stream_id = self._event_stream_id(event)

        self._streams.setdefault(stream_id, []).append(event)
        self._events.append(event)

    def append_to_stream(
        self,
        stream_id: str,
        events: Tuple[Any, ...],
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Atomically append events to a stream if the expected version matches.

        Version semantics:
            empty stream = 0
            one event     = 1
            two events    = 2
        """
        if not stream_id:
            raise EventStoreError("stream_id cannot be empty")

        if not isinstance(events, tuple):
            raise TypeError("events must be provided as a tuple")

        stream = self._streams.setdefault(stream_id, [])
        current_version = len(stream)

        if expected_version is not None and expected_version != current_version:
            raise StreamConcurrencyError(
                f"Stream '{stream_id}' concurrency violation: "
                f"expected version {expected_version}, "
                f"actual version {current_version}."
            )

        if not events:
            return current_version

        # Validate the entire batch before mutating anything.
        for event in events:
            event_stream_id = self._event_stream_id(event)

            if event_stream_id != stream_id:
                raise EventStoreError(
                    f"Event belongs to stream '{event_stream_id}', "
                    f"not '{stream_id}'."
                )

        stream.extend(events)
        self._events.extend(events)

        return len(stream)

    def read_stream(self, stream_id: str) -> Tuple[Any, ...]:
        """
        Return the complete immutable history of one stream.
        """
        return tuple(self._streams.get(stream_id, ()))

    def get_stream(self, aggregate_id: str) -> Tuple[Any, ...]:
        """
        Compatibility alias for aggregate/stream reads.
        """
        return self.read_stream(aggregate_id)

    def get_events(self) -> Tuple[Any, ...]:
        """
        Return all events as an immutable tuple.
        """
        return tuple(self._events)

    @staticmethod
    def _event_stream_id(event: Any) -> Optional[str]:
        """
        Resolve the event's stream identity.

        Current OMS events use intent_id.
        Older domain events may use aggregate_id/order_id.
        """
        return getattr(
            event,
            "intent_id",
            getattr(
                event,
                "aggregate_id",
                getattr(event, "order_id", None),
            ),
        )


class InMemoryEventStore(ImmutableEventStore):
    """
    Compatibility/public name used by integration tests and application code.

    The implementation remains ImmutableEventStore.
    """

    pass