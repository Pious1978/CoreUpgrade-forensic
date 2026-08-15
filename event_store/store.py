from contracts.events import DomainEvent

class InMemoryEventStore:
    """In-memory event store supporting event sourcing and domain event streams."""

    def __init__(self):
        self.events = []

    def append(self, event: DomainEvent):
        self.events.append(event)

    def get_stream(self, aggregate_id: str):
        return [e for e in self.events if e.aggregate_id == aggregate_id]
