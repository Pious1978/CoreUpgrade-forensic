from enum import Enum
from contracts.research import ResearchSignalContract
from contracts.governance import ResearchApprovedContract
from contracts.portfolio import PortfolioIntentContract, PortfolioDecisionContract
from contracts.execution import ExecutionPlanContract, ExecutionResultContract
from contracts.learning import PerformanceFeedbackContract

VSC_PIPELINE_VERSION = "1.0"

class TrustLevel(str, Enum):
    RAW = "RAW"
    GOVERNANCE_CERTIFIED = "GOVERNANCE_CERTIFIED"
    ANALYTICAL = "ANALYTICAL"

class LifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    APPROVED = "APPROVED"
    DRAFT = "DRAFT"
    ROUTING = "ROUTING"
    SETTLED = "SETTLED"
    RECORDED = "RECORDED"

STRUCTURAL_INVARIANTS = {
    "chain_length": 7,
    "contract_types": (
        ResearchSignalContract,
        ResearchApprovedContract,
        PortfolioIntentContract,
        PortfolioDecisionContract,
        ExecutionPlanContract,
        ExecutionResultContract,
        PerformanceFeedbackContract,
    ),
}

BUSINESS_INVARIANTS = {
    "trust_transitions": (
        TrustLevel.RAW,
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.GOVERNANCE_CERTIFIED,
        TrustLevel.ANALYTICAL,
    ),
    "lifecycle_states": (
        LifecycleState.ACTIVE,
        LifecycleState.APPROVED,
        LifecycleState.DRAFT,
        LifecycleState.ACTIVE,
        LifecycleState.ROUTING,
        LifecycleState.SETTLED,
        LifecycleState.RECORDED,
    ),
    "domain_sequence": (
        "RESEARCH",
        "GOVERNANCE",
        "PORTFOLIO",
        "PORTFOLIO_RISK",
        "EXECUTION_PLANNING",
        "EXECUTION_BROKER",
        "LEARNING",
    ),
}
