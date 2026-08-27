from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from oms.state_machine.order_state_machine import OrderState


@dataclass(frozen=True, slots=True)
class BaseOrderEvent:
    event_id: str
    intent_id: str
    execution_trace_id: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id cannot be empty")
        if not self.intent_id.strip():
            raise ValueError("intent_id cannot be empty")
        if not self.execution_trace_id.strip():
            raise ValueError("execution_trace_id cannot be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OrderSubmittedEvent(BaseOrderEvent):
    broker_order_id: str
    exchange_order_id: Optional[str]


@dataclass(frozen=True, slots=True)
class OrderTransitionEvent(BaseOrderEvent):
    from_state: OrderState
    to_state: OrderState
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Optional[Decimal]


@dataclass(frozen=True, slots=True)
class OrderRejectedEvent(BaseOrderEvent):
    reason: str
    source: str


@dataclass(frozen=True, slots=True)
class OrderExecutionErrorEvent(BaseOrderEvent):
    """Emitted when a systemic, network, or integration error prevents execution.
    
    This does NOT imply the order was rejected by the exchange, but rather that
    the OMS cannot confirm the order's state.
    """
    error_message: str
    error_type: str
