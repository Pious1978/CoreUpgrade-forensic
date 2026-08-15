from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from contracts.base_contract import BaseContract

class ContractType(Enum):
    PERFORMANCE_FEEDBACK = "PerformanceFeedbackContract"

@dataclass(frozen=True)
class PerformanceAttributionContract(BaseContract):
    contract_type: ContractType = ContractType.PERFORMANCE_FEEDBACK
    portfolio_id: str = ""
    initial_capital: float = 0.0
    final_portfolio_value: float = 0.0
    cumulative_return_pct: float = 0.0
    realized_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    attribution_breakdown: dict = field(default_factory=dict)
    execution_quality_report: dict = field(default_factory=dict)
    signal_learning_feedback: dict = field(default_factory=dict)
