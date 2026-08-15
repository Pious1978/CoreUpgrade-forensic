from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    timestamp: datetime
    mode: str  # BACKTEST, PAPER, LIVE
    correlation_id: str
