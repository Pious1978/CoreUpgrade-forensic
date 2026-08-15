from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class BacktestResult:
    signal_id: str
    oos_sharpe: float
    walk_forward_pass_rate: float
    capacity_limit_usd: float
    metrics: Dict[str, float]
