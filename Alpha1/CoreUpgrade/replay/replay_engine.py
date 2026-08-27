import time

from event_store.store_protocol import EventStore
from replay.models import ReplayResult
from replay.projection_registry import ProjectionRegistry


class ReplayEngine:
    """Deterministic orchestrator that reconstructs system state from immutable facts."""

    def __init__(self, store: EventStore, registry: ProjectionRegistry) -> None:
        self._store = store
        self._registry = registry

    def replay(self, stream_id: str) -> ReplayResult:
        """Fetches a stream and broadcasts guaranteed facts to all registered projections."""
        start_time = time.perf_counter()

        # The EventStore guarantees these are cryptographically verified, upcasted, 
        # and strictly ordered by stream_version.
        events = self._store.read_stream(stream_id)

        version = 0
        for event in events:
            version += 1
            for projection in self._registry.projections():
                projection.apply(event)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return ReplayResult(
            stream_id=stream_id,
            version=version,
            replayed_events=len(events),
            duration_ms=duration_ms
        )
