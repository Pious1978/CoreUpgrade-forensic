from typing import Tuple, Optional
from uuid import UUID
from .event_repository import EventRepository
from .transaction_manager import AbstractTransactionManager
from ..event_store import StoredEvent
from ..events import PromotionDomainEvent

class PostgresEventRepository(EventRepository):
    """PostgreSQL production adapter implementing EventRepository."""
    def __init__(self, tx_manager: AbstractTransactionManager) -> None:
        self.tx_manager = tx_manager

    def append(
        self,
        stream_id: UUID,
        event: PromotionDomainEvent,
        event_version: int = 1,
        expected_sequence: Optional[int] = None,
        correlation_id: UUID = None,
        causation_id: UUID = None
    ) -> StoredEvent:
        # SQL execution adapter integration point for v2.8
        raise NotImplementedError("PostgresEventRepository.append will be wired in v2.8.")

    def load_stream(self, stream_id: UUID) -> Tuple[StoredEvent, ...]:
        raise NotImplementedError("PostgresEventRepository.load_stream will be wired in v2.8.")
