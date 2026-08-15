from dataclasses import dataclass
from decimal import Decimal
from contracts.broker.enums import OrderSide

@dataclass(frozen=True)
class ExecutionContract:
    execution_id: str
    order_id: str
    symbol: str
    side: OrderSide
    filled_quantity: Decimal
    fill_price: Decimal
    commission: Decimal
    timestamp: int
    exchange_trade_id: str
    correlation_id: str
    broker_name: str

    def __post_init__(self):
        if self.filled_quantity <= 0:
            raise ValueError("Filled quantity must be positive")
        if self.fill_price <= 0:
            raise ValueError("Fill price must be positive")
