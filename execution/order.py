from dataclasses import dataclass
from datetime import datetime

@dataclass
class Order:
    """
    Standardized institutional order contract for execution simulation and routing.
    """
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    limit_price: float = None
    urgency: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH"
    max_participation: float = 0.10
    arrival_time: datetime = None
    time_in_force: str = "DAY"
    strategy: str = "VCP_BREAKOUT"
    expected_alpha_decay: float = 0.01
