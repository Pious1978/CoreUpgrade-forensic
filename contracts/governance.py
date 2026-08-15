from dataclasses import dataclass
from contracts.base_contract import BaseContract

@dataclass(frozen=True)
class ResearchApprovedContract(BaseContract):
    contract_type: str = "ResearchApprovedContract"
    domain: str = "GOVERNANCE"
    trust_level: str = "GOVERNANCE_CERTIFIED"
    lifecycle_state: str = "APPROVED"
    signal_id: str = "sig-001"
    symbol: str = "AAPL"
    approved_weight: float = 0.10
    approval_reason: str = "Passed confidence gate."
