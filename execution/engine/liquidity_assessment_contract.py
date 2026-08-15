from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class LiquidityAssessment:
    available_quantity: Decimal
    liquidity_score: Decimal
    estimated_fill_probability: Decimal

    def __post_init__(self) -> None:
        if self.available_quantity < Decimal("0"):
            raise ValueError("Available quantity cannot be negative.")
        if not (Decimal("0") <= self.liquidity_score <= Decimal("1")):
            raise ValueError("Liquidity score must be between 0 and 1.")
        if not (Decimal("0") <= self.estimated_fill_probability <= Decimal("1")):
            raise ValueError("Estimated fill probability must be between 0 and 1.")
