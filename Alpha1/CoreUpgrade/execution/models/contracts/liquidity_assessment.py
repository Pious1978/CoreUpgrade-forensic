from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class LiquidityAssessment:
    available_quantity: Decimal
    fill_probability: Decimal
    liquidity_score: Decimal

    def __post_init__(self) -> None:
        if self.available_quantity < Decimal("0"):
            raise ValueError("Available quantity cannot be negative.")
        if not (Decimal("0") <= self.fill_probability <= Decimal("1")):
            raise ValueError("Fill probability must be between 0 and 1.")
        if not (Decimal("0") <= self.liquidity_score <= Decimal("1")):
            raise ValueError("Liquidity score must be between 0 and 1.")
