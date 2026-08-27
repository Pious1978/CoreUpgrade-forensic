from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping
from uuid import UUID, uuid4

@dataclass(frozen=True)
class Position:
    symbol: str
    shares: float
    average_cost: float
    last_price: float

    @property
    def market_value(self) -> float:
        return self.shares * self.last_price

@dataclass(frozen=True)
class PortfolioSnapshot:
    portfolio_id: str
    snapshot_id: UUID = field(default_factory=uuid4)
    previous_snapshot_id: UUID = None
    version: int = 1
    root_contract_id: UUID = None
    correlation_id: UUID = None
    capital_base: float = 0.0
    cash_balance: float = 0.0
    holdings: Mapping[str, Position] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_portfolio_value(self) -> float:
        holdings_value = sum(p.market_value for p in self.holdings.values())
        return self.cash_balance + holdings_value
