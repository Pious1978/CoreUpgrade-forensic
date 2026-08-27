from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class SignalValidationResult:
    signal_id: str
    verdict: str  # PASS | CONDITIONAL | FAIL

    oos_sharpe: float
    deflated_sharpe: float
    p_value: float

    capacity_limit: float
    allowed_regimes: List[str]

    validation_timestamp: datetime
