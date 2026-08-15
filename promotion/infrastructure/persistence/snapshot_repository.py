from abc import ABC, abstractmethod
from typing import Optional, Any
from uuid import UUID

class SnapshotRepository(ABC):
    """Manages aggregate state snapshots for large event-sourced streams."""
    @abstractmethod
    def save_snapshot(self, stream_id: UUID, version: int, state: Any) -> None: pass
    @abstractmethod
    def load_snapshot(self, stream_id: UUID) -> Optional[Any]: pass
