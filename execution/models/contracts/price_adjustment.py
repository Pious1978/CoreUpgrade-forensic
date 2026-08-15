from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PriceAdjustment:
    spread_component: Decimal
    volatility_component: Decimal
    impact_component: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.spread_component < Decimal("0"):
            raise ValueError("Spread component cannot be negative.")
        if self.volatility_component < Decimal("0"):
            raise ValueError("Volatility component cannot be negative.")

    @property
    def total(self) -> Decimal:
        """Aggregates all active price adjustment components into a single net modifier."""
        return self.spread_component + self.volatility_component + self.impact_component
