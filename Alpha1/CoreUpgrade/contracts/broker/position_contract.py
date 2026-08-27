from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class PositionContract:
    portfolio_id: str
    symbol: str
    quantity: Decimal
    average_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    timestamp: int
