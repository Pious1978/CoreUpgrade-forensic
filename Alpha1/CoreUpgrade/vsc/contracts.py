from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone

@dataclass(frozen=True)
class ResearchSignalContract:
    contract_type: str = "ResearchSignalContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "RESEARCH"
    signal_id: str = "sig-001"
    symbol: str = "AAPL"
    suggested_weight: float = 0.10
    confidence_score: float = 0.85
    lifecycle_state: str = "ACTIVE"
    trust_level: str = "RAW"

@dataclass(frozen=True)
class ResearchApprovedContract:
    contract_type: str = "ResearchApprovedContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "GOVERNANCE"
    parent_contract_id: UUID = None
    signal_id: str = "sig-001"
    symbol: str = "AAPL"
    approved_weight: float = 0.10
    approval_reason: str = "Passed confidence gate."
    lifecycle_state: str = "APPROVED"
    trust_level: str = "GOVERNANCE_CERTIFIED"

@dataclass(frozen=True)
class PortfolioIntentContract:
    contract_type: str = "PortfolioIntentContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "PORTFOLIO"
    parent_contract_id: UUID = None
    intent_id: str = "intent-001"
    symbol: str = "AAPL"
    target_weight: float = 0.10
    lifecycle_state: str = "DRAFT"
    trust_level: str = "GOVERNANCE_CERTIFIED"

@dataclass(frozen=True)
class PortfolioDecisionContract:
    contract_type: str = "PortfolioDecisionContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "PORTFOLIO_RISK"
    parent_contract_id: UUID = None
    decision_id: str = "decision-001"
    symbol: str = "AAPL"
    approved_weight: float = 0.10
    risk_score: float = 0.12
    lifecycle_state: str = "ACTIVE"
    trust_level: str = "GOVERNANCE_CERTIFIED"

@dataclass(frozen=True)
class ExecutionPlanContract:
    contract_type: str = "ExecutionPlanContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "EXECUTION_PLANNING"
    parent_contract_id: UUID = None
    plan_id: str = "plan-001"
    symbol: str = "AAPL"
    target_quantity: float = 1000.0
    order_type: str = "TWAP"
    lifecycle_state: str = "ROUTING"
    trust_level: str = "GOVERNANCE_CERTIFIED"

@dataclass(frozen=True)
class ExecutionResultContract:
    contract_type: str = "ExecutionResultContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "EXECUTION_BROKER"
    parent_contract_id: UUID = None
    result_id: str = "result-001"
    symbol: str = "AAPL"
    executed_quantity: float = 1000.0
    average_fill_price: float = 175.50
    venue: str = "PAPER_BROKER"
    lifecycle_state: str = "SETTLED"
    trust_level: str = "GOVERNANCE_CERTIFIED"

@dataclass(frozen=True)
class PerformanceFeedbackContract:
    contract_type: str = "PerformanceFeedbackContract"
    immutable_id: UUID = field(default_factory=uuid4)
    version: int = 1
    domain: str = "LEARNING"
    parent_contract_id: UUID = None
    feedback_id: str = "fb-001"
    symbol: str = "AAPL"
    expected_price: float = 175.00
    executed_price: float = 175.50
    realized_pnl: float = 500.0
    execution_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lifecycle_state: str = "RECORDED"
    trust_level: str = "ANALYTICAL"
