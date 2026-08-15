from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PriceAdjustment:
    base_price: Decimal
    slippage: Decimal
    market_impact: Decimal

    @property
    def execution_price(self) -> Decimal:
        """Enforces the structural price decomposition invariant in one shared place."""
        return self.base_price + self.slippage + self.market_impact
