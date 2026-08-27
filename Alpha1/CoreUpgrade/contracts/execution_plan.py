from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ExecutionPlanContract:
    """Public boundary routing contract."""
    symbol: str
    target_shares: int
    algo_strategy: str
    price_limit: float
    timestamp: datetime
