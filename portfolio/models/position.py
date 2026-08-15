from dataclasses import dataclass
from decimal import Decimal

from portfolio.exceptions import PortfolioProjectionError


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable read-model representing an asset holding."""
    symbol: str
    quantity: Decimal
    average_cost: Decimal

    def apply_fill(self, fill_qty: Decimal, fill_price: Decimal) -> 'Position':
        """Mathematically derives a new Position from a specific execution."""
        if fill_qty == Decimal("0"):
            return self

        new_qty = self.quantity + fill_qty
        
        if new_qty < Decimal("0"):
            # In a long-only portfolio, this indicates corrupted stream history
            raise PortfolioProjectionError(f"Fill resulted in negative position for {self.symbol}")
            
        if new_qty == Decimal("0"):
            return Position(symbol=self.symbol, quantity=Decimal("0"), average_cost=Decimal("0"))
            
        current_notional = self.quantity * self.average_cost
        fill_notional = fill_qty * fill_price
        
        new_avg_cost = (current_notional + fill_notional) / new_qty

        return Position(
            symbol=self.symbol,
            quantity=new_qty,
            average_cost=new_avg_cost
        )
