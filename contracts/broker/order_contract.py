from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from contracts.broker.enums import OrderSide, OrderType

@dataclass(frozen=True)
class OrderContract:
    order_id: str
    portfolio_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    limit_price: Optional[Decimal]
    timestamp: int
    strategy_id: str
    decision_hash: str
    correlation_id: str
    broker_name: str

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if self.order_type == OrderType.LIMIT and (self.limit_price is None or self.limit_price <= 0):
            raise ValueError("Limit order requires a valid positive limit price")
