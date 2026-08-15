from dataclasses import dataclass

@dataclass(frozen=True)
class BrokerAcceptedEvent:
    order_id: str
    broker_order_id: str
    broker: str
    timestamp: int
    correlation_id: str

@dataclass(frozen=True)
class OrderRejectedEvent:
    order_id: str
    error_message: str
    broker: str
    timestamp: int
    correlation_id: str
