from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from contracts.base_contract import BaseContract

class ContractType(Enum):
    STRATEGY_VALIDATION = "StrategyValidationContract"

@dataclass(frozen=True)
class StrategyValidationContract(BaseContract):
    contract_type: ContractType = ContractType.STRATEGY_VALIDATION
    strategy_id: str = ""
    status: str = "REJECTED"  # APPROVED / REJECTED
    validation_score: float = 0.0
    failures: tuple = field(default_factory=tuple)
    validator_version: str = "1.0"
