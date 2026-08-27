from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

@dataclass(frozen=True)
class OrderSubmittedEvent:
    client_order_id: str
    broker_order_id: str
    timestamp: int

@dataclass(frozen=True)
class OrderAcceptedEvent:
    client_order_id: str
    broker_order_id: str
    timestamp: int

@dataclass(frozen=True)
class PartialFillEvent:
    client_order_id: str
    filled_quantity: Decimal
    fill_price: Decimal
    timestamp: int

@dataclass(frozen=True)
class FillReceivedEvent:
    client_order_id: str
    filled_quantity: Decimal
    fill_price: Decimal
    timestamp: int

@dataclass(frozen=True)
class PositionUpdatedEvent:
    symbol: str
    new_quantity: Decimal
    average_price: Decimal
    timestamp: int

@dataclass(frozen=True)
class AccountUpdatedEvent:
    new_cash_balance: Decimal
    timestamp: int

@dataclass(frozen=True)
class OrderCancelledEvent:
    client_order_id: str
    timestamp: int

@dataclass(frozen=True)
class OrderRejectedEvent:
    client_order_id: str
    reason: str
    timestamp: int

@dataclass(frozen=True)
class OrderCompletedEvent:
    client_order_id: str
    status: OrderStatus
    timestamp: int

class EventDispatcher(Protocol):
    def emit(self, event) -> None:
        ...
