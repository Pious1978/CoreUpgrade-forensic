from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from contracts.base_contract import BaseContract

class ContractType(Enum):
    PORTFOLIO_DECISION = "PortfolioDecisionContract"
    PORTFOLIO_RISK = "PortfolioRiskContract"

@dataclass(frozen=True)
class PortfolioRiskContract(BaseContract):
    contract_type: ContractType = ContractType.PORTFOLIO_DECISION
    portfolio_id: str = ""
    parent_snapshot_id: UUID = None
    portfolio_value: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    max_drawdown: float = 0.0
    concentration_score: float = 0.0
    risk_status: str = "APPROVED"
