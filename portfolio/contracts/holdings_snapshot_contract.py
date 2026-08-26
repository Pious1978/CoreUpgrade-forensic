from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionHolding:
    """Represents an existing held position in the account."""
    symbol: str
    quantity: Decimal
    average_price: Decimal

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if self.quantity < Decimal("0"):
            raise ValueError("Holding quantity cannot be negative.")
        if self.average_price < Decimal("0"):
            raise ValueError("Average price cannot be negative.")


@dataclass(frozen=True, slots=True)
class HoldingsSnapshotContract:
    """
    Immutable point-in-time snapshot of current account positions and cash,
    providing precise provenance for portfolio rebalancing.
    """
    snapshot_id: str
    account_id: str
    holdings: tuple[PositionHolding, ...]
    cash_balance: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("Snapshot ID cannot be empty.")
        if not self.account_id:
            raise ValueError("Account ID cannot be empty.")
        if self.cash_balance < Decimal("0"):
            raise ValueError("Cash balance cannot be negative.")