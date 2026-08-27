from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PositionTargetContract:
    """
    Defines the target quantity, capital weight, asset class, and currency 
    for a specific symbol as determined by portfolio optimization.
    """
    symbol: str
    target_weight: Decimal
    target_quantity: Decimal
    asset_class: str
    currency: str
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if not self.asset_class:
            raise ValueError("Asset class cannot be empty.")
        if not self.currency:
            raise ValueError("Currency cannot be empty.")
        if self.target_quantity < Decimal("0"):
            raise ValueError("Target quantity cannot be negative.")
        if not (Decimal("0") <= self.target_weight <= Decimal("1")):
            raise ValueError("Target weight must be between 0 and 1 (0% to 100%).")
