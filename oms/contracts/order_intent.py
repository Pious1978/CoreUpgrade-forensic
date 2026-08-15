from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True, slots=True)
class OrderIntentContract:
    """Immutable contract representing a certified, risk-approved trading intent

    ready for OMS intake and broker routing.
    """
    intent_id: str
    portfolio_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]  # None for MARKET orders
    currency: str
    risk_request_id: str
    execution_trace_id: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.intent_id.strip():
            raise ValueError("intent_id cannot be empty")
        if not self.portfolio_id.strip():
            raise ValueError("portfolio_id cannot be empty")
        if not self.strategy_id.strip():
            raise ValueError("strategy_id cannot be empty")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        if self.order_type == OrderType.LIMIT and (self.price is None or self.price <= Decimal("0")):
            raise ValueError("LIMIT orders require a positive price")
        if not self.currency.strip():
            raise ValueError("currency cannot be empty")
        if not self.risk_request_id.strip():
            raise ValueError("risk_request_id cannot be empty")
        if not self.execution_trace_id.strip():
            raise ValueError("execution_trace_id cannot be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
