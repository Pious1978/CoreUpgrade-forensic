from dataclasses import dataclass
from enum import Enum

class CertificationStatus(Enum):
    CERTIFIED = "CERTIFIED"
    REJECTED = "REJECTED"

class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    message: str
    severity: Severity
    validator_name: str

@dataclass(frozen=True, slots=True)
class ValidationResult:
    test_id: str
    status: CertificationStatus
    violations: tuple[Violation, ...]
    execution_trace_id: str
