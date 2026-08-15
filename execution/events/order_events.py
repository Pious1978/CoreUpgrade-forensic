from dataclasses import dataclass

@dataclass(frozen=True)
class OrderIntentCreatedEvent:
    order_id: str
    strategy_id: str
    timestamp: int
    correlation_id: str

@dataclass(frozen=True)
class OrderSubmissionRequestedEvent:
    order_id: str
    broker: str
    timestamp: int
    correlation_id: str

@dataclass(frozen=True)
class OrderCancelledEvent:
    order_id: str
    broker: str
    timestamp: int
    correlation_id: str
