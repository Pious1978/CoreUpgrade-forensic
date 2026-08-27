from dataclasses import dataclass
from contracts.base_contract import BaseContract

@dataclass(frozen=True)
class ResearchSignalContract(BaseContract):
    contract_type: str = "ResearchSignalContract"
    domain: str = "RESEARCH"
    trust_level: str = "RAW"
    lifecycle_state: str = "ACTIVE"
    signal_id: str = "sig-001"
    symbol: str = "AAPL"
    suggested_weight: float = 0.10
    confidence_score: float = 0.85
    expected_return: float = 0.05
