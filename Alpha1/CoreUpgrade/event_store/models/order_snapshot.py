from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from oms.contracts.order_intent import OrderIntentContract
from oms.state_machine.order_state_machine import OrderState


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    """Immutable read-model representing the derived point-in-time state of an order,
    combining the original intent with the folded event history.
    """
    intent: OrderIntentContract
    state: OrderState
    broker_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    latest_error: Optional[str] = None
    last_updated_at: Optional[datetime] = None
