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
    """
    Immutable snapshot container representing a pre-trade risk check request.

    Designed for complete determinism and historical replayability.

    Derived values such as order_notional are exposed as read-only
    properties rather than stored mutable state.
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
    currency: str
    timestamp: datetime

    def __post_init__(self) -> None:
        """Enforces basic structural invariants upon instantiation."""

        if self.quantity <= Decimal("0"):
            raise ValueError(
                f"RiskCheckRequest quantity must be positive, got {self.quantity}"
            )

        if self.price <= Decimal("0"):
            raise ValueError(
                f"RiskCheckRequest price must be positive, got {self.price}"
            )

        if self.portfolio_value <= Decimal("0"):
            raise ValueError(
                "RiskCheckRequest portfolio_value must be positive, "
                f"got {self.portfolio_value}"
            )

        if not self.currency:
            raise ValueError(
                "RiskCheckRequest currency must be non-empty"
            )

    @property
    def order_notional(self) -> Decimal:
        """
        Deterministic gross notional value of the proposed order.

        quantity × price

        This is intentionally derived from immutable request state rather
        than stored as a separate field, preventing inconsistent snapshots.
        """
        return self.quantity * self.price