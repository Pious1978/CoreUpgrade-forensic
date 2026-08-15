from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class DecisionContext:
    experiment_id: str
    timestamp: str
    nav: float
    cash: float

@dataclass(frozen=True)
class OptimizationResult:
    target_weights: Dict[str, float]
    expected_turnover: float

@dataclass(frozen=True)
class RiskAssessment:
    portfolio_beta: float
    annualized_volatility: float
    expected_shortfall: float

@dataclass(frozen=True)
class ComplianceAssessment:
    passed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class GovernanceDecision:
    status: str  # "PASS", "WARN", "SOFT_BLOCK", "HARD_BLOCK"
    action: str
    reason: str
    violations: List[Dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class ExecutionPlan:
    approved_orders: List[Dict[str, Any]]
    execution_style: str
    estimated_cost_bps: float
