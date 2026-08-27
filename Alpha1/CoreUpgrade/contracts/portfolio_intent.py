from dataclasses import dataclass
from typing import Dict
from datetime import datetime

@dataclass(frozen=True)
class PortfolioIntentContract:
    """Public boundary contract between Portfolio and Execution."""
    target_weights: Dict[str, float]
    rebalance_timestamp: datetime
    execution_urgency: str
