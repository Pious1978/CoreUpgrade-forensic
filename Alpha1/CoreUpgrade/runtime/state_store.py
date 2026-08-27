from dataclasses import dataclass, field
from typing import Dict

@dataclass
class ProductionStateStore:
    """Maintains active operational portfolio state across production cycles."""
    portfolio_id: str = "PORTFOLIO-ALPHA-01"
    cash: float = 1000000.0
    holdings: Dict[str, float] = field(default_factory=dict)
    pending_orders: list = field(default_factory=list)
    active_strategy_id: str = "STRAT-MOMENTUM-V1"
    risk_state: str = "NORMAL"

    def update_state(self, cash: float, holdings: dict, risk_state: str = "NORMAL"):
        self.cash = cash
        self.holdings = holdings
        self.risk_state = risk_state
