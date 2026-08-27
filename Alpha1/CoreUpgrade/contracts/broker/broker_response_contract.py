from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from contracts.broker.enums import OrderStatus

@dataclass(frozen=True)
class BrokerResponseContract:
    order_id: str
    broker_order_id: Optional[str]
    status: OrderStatus
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Optional[Decimal]
    error_message: Optional[str]
    timestamp: int
    correlation_id: str
    broker_name: str

    def __post_init__(self):
        if self.filled_quantity < 0 or self.remaining_quantity < 0:
            raise ValueError("Quantities cannot be negative")
