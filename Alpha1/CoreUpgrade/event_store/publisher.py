from typing import Protocol
from contracts.events import DomainEvent

class EventPublisherProtocol(Protocol):
    """Defines the decoupled contract for publishing immutable domain events."""
    def publish(self, event: DomainEvent) -> None: ...
