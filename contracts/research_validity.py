from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ResearchValidityResult:
    """
    The ultimate alpha contract. The Portfolio Optimizer will only allocate 
    capital if a signal possesses a PASSING verdict on this contract.
    """
    signal_id: str
    oos_sharpe: float
    deflated_sharpe: float
    walk_forward_pass_rate: float
    capacity_limit: float
    survivorship_bias_check: bool
    lookahead_bias_check: bool
    transaction_cost_adjusted: bool
    verdict: str
    validation_timestamp: datetime
