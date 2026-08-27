from dataclasses import dataclass
from contracts.base_contract import BaseContract

@dataclass(frozen=True)
class PortfolioIntentContract(BaseContract):
    contract_type: str = "PortfolioIntentContract"
    domain: str = "PORTFOLIO"
    trust_level: str = "GOVERNANCE_CERTIFIED"
    lifecycle_state: str = "DRAFT"
    intent_id: str = "intent-001"
    symbol: str = "AAPL"
    target_weight: float = 0.10

@dataclass(frozen=True)
class PortfolioDecisionContract(BaseContract):
    contract_type: str = "PortfolioDecisionContract"
    domain: str = "PORTFOLIO_RISK"
    trust_level: str = "GOVERNANCE_CERTIFIED"
    lifecycle_state: str = "ACTIVE"
    decision_id: str = "decision-001"
    symbol: str = "AAPL"
    approved_weight: float = 0.10
    risk_score: float = 0.12
