from dataclasses import dataclass
from typing import Any, Protocol

from oms.events.base import BaseOrderEvent


class Projection(Protocol):
    """Universal protocol for any read-model consumer in the architecture."""
    
    def apply(self, event: BaseOrderEvent) -> None:
        """Processes an event and mutates internal projection state."""
        ...

    def snapshot(self) -> Any:
        """Returns the current point-in-time state of the projection."""
        ...


@dataclass(slots=True)
class ReplayContext:
    """Tracks the state of an active replay execution."""
    stream_id: str
    current_version: int
    event_count: int


@dataclass(frozen=True)
class ReplayResult:
    """Immutable diagnostic result of a completed replay."""
    stream_id: str
    version: int
    replayed_events: int
    duration_ms: float
