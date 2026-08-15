from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class FillReceivedEvent:
    execution_id: str
    order_id: str
    filled_quantity: Decimal
    fill_price: Decimal
    broker: str
    timestamp: int
    correlation_id: str
