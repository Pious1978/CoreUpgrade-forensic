from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExecutionReport:
    order_id: str
    symbol: str
    requested_quantity: float
    filled_quantity: float
    avg_fill_price: float
    slippage_bps: float
    execution_timestamp: datetime
