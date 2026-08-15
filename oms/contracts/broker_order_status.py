from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from oms.state_machine.order_state_machine import OrderState


@dataclass(frozen=True, slots=True)
class BrokerOrderStatus:
    """Immutable normalized contract representing the current status of an order 
    at the external broker.
    """
    broker_order_id: str
    state: OrderState
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Optional[Decimal]

    def __post_init__(self) -> None:
        if not self.broker_order_id.strip():
            raise ValueError("broker_order_id cannot be empty")
            
        if not isinstance(self.state, OrderState):
            raise TypeError(f"state must be an OrderState, got {type(self.state)}")

        if self.filled_quantity < Decimal("0"):
            raise ValueError("filled_quantity cannot be negative")
            
        if self.remaining_quantity < Decimal("0"):
            raise ValueError("remaining_quantity cannot be negative")

        # Logical invariants for fills
        if self.filled_quantity > Decimal("0"):
            if self.average_fill_price is None or self.average_fill_price <= Decimal("0"):
                raise ValueError("A positive filled_quantity requires a valid average_fill_price")
