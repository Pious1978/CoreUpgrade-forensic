from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple, List
from core.contract_runtime import ContractBase

class GovernanceActionType(Enum):
    EXECUTE = "EXECUTE"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"
    REPAIR = "REPAIR"
    ABORT = "ABORT"

@dataclass(frozen=True)
class DomainEvent(ContractBase):
    schema_version: str = "1.0"
    run_id: str = ""
    correlation_id: str = ""
    sequence: int = 0
    domain: str = ""
    stage: str = ""
    timestamp: datetime = None
    input_fingerprint: str = ""
    output_fingerprint: str = ""

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not self.run_id: errors.append("Missing run_id")
        if not self.correlation_id: errors.append("Missing correlation_id")
        if self.sequence < 0: errors.append("Invalid sequence number")
        if not self.domain: errors.append("Missing domain")
        if not self.stage: errors.append("Missing stage")
        return len(errors) == 0, errors