from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

@dataclass(frozen=True, slots=True)
class FillContract:
    fill_id: UUID
    execution_id: UUID
    client_order_id: str
    symbol: str
    quantity: Decimal
    price: Decimal
    timestamp: int
    fee: Decimal

    def __post_init__(self) -> None:
        if self.quantity <= Decimal("0"):
            raise ValueError("Fill quantity must be positive.")

        if self.price <= Decimal("0"):
            raise ValueError("Fill price must be positive.")

        if self.fee < Decimal("0"):
            raise ValueError("Fill fee cannot be negative.")

    @property
    def notional_value(self) -> Decimal:
        """Derives the total notional financial value of the atomic fill event."""
        return self.quantity * self.price
