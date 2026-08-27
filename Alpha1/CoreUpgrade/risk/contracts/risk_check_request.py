from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    """Enumeration representing order sides for risk evaluation."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class RiskCheckRequest:
    """Immutable snapshot container representing a pre-trade risk check request.

    Designed for complete determinism and historical replayability.
    """
    request_id: str
    portfolio_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    current_position: Decimal
    portfolio_value: Decimal
    daily_pnl: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        """Enforces basic structural invariants upon instantiation."""
        if self.quantity <= Decimal("0"):
            raise ValueError(f"RiskCheckRequest quantity must be positive, got {self.quantity}")
        if self.price <= Decimal("0"):
            raise ValueError(f"RiskCheckRequest price must be positive, got {self.price}")
        if self.portfolio_value <= Decimal("0"):
            raise ValueError(f"RiskCheckRequest portfolio_value must be positive, got {self.portfolio_value}")
