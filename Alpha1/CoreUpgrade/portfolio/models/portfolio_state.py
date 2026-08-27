from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, FrozenSet

from portfolio.models.position import Position


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Immutable projection of a portfolio's real-time balances and positions."""
    portfolio_id: str
    cash_balance: Decimal
    positions: Dict[str, Position] = field(default_factory=dict)
    
    # Replay metadata: prevents double-counting if a webhook is processed twice
    applied_fills: FrozenSet[str] = field(default_factory=frozenset)
