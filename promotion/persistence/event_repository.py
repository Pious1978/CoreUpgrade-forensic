from abc import ABC, abstractmethod
from typing import Tuple, Optional
from uuid import UUID
from ..event_store import StoredEvent
from ..events import PromotionDomainEvent

class EventRepository(ABC):
    """Abstract persistence repository for event-sourced promotion streams."""
    @abstractmethod
    def append(
        self,
        stream_id: UUID,
        event: PromotionDomainEvent,
        event_version: int = 1,
        expected_sequence: Optional[int] = None,
        correlation_id: UUID = None,
        causation_id: UUID = None
    ) -> StoredEvent: pass

    @abstractmethod
    def load_stream(self, stream_id: UUID) -> Tuple[StoredEvent, ...]: pass
