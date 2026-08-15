from dataclasses import dataclass, field
from datetime import datetime, timezone
from contracts.base_contract import BaseContract

@dataclass(frozen=True)
class PerformanceFeedbackContract(BaseContract):
    contract_type: str = "PerformanceFeedbackContract"
    domain: str = "LEARNING"
    trust_level: str = "ANALYTICAL"
    lifecycle_state: str = "RECORDED"
    feedback_id: str = "fb-001"
    symbol: str = "AAPL"
    expected_price: float = 175.00
    executed_price: float = 175.50
    realized_pnl: float = 1250.00
    expected_return: float = 0.05
    realized_return: float = 0.052
    holding_period_days: int = 1
    execution_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
