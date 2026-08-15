from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from contracts.base_contract import BaseContract

class ContractType(Enum):
    EXECUTION_DECISION = "ExecutionDecisionContract"

@dataclass(frozen=True)
class ExecutionDecisionContract(BaseContract):
    contract_type: ContractType = ContractType.EXECUTION_DECISION
    portfolio_id: str = ""
    parent_risk_id: UUID = None
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    selected_strategy: str = "TWAP"
    expected_spread_cost: float = 0.0
    market_impact: float = 0.0
    estimated_slippage: float = 0.0
    urgency: str = "MEDIUM"
    execution_status: str = "OPTIMIZED"
