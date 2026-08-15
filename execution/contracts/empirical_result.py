from dataclasses import dataclass
from typing import Dict, Any, List
from enum import Enum
from types import MappingProxyType

class CertificationState(Enum):
    FAILED = "FAILED"
    CERTIFIED = "CERTIFIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

@dataclass(frozen=True)
class ExecutionEmpiricalResult:
    state: CertificationState
    master_proof_hash: str
    proof_payload: Dict[str, Any]
    diagnostics: MappingProxyType
    execution_order: List[str]
    results: Dict[str, Any]