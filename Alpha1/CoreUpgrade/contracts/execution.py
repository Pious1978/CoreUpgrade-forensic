from dataclasses import dataclass
from contracts.base_contract import BaseContract

@dataclass(frozen=True)
class ExecutionPlanContract(BaseContract):
    contract_type: str = "ExecutionPlanContract"
    domain: str = "EXECUTION_PLANNING"
    trust_level: str = "GOVERNANCE_CERTIFIED"
    lifecycle_state: str = "ROUTING"
    plan_id: str = "plan-001"
    symbol: str = "AAPL"
    target_quantity: float = 1000.0
    order_type: str = "TWAP"

@dataclass(frozen=True)
class ExecutionResultContract(BaseContract):
    contract_type: str = "ExecutionResultContract"
    domain: str = "EXECUTION_BROKER"
    trust_level: str = "GOVERNANCE_CERTIFIED"
    lifecycle_state: str = "SETTLED"
    result_id: str = "result-001"
    symbol: str = "AAPL"
    executed_quantity: float = 1000.0
    average_fill_price: float = 175.50
    venue: str = "PAPER_BROKER"
    slippage: float = 0.0
    commission: float = 1.00
    latency_ms: float = 12.5
    fill_ratio: float = 1.0
    market_impact: float = 0.0001
