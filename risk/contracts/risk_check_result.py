from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from risk.contracts.risk_violation import RiskViolation


class RiskStatus(str, Enum):
    """Enumeration representing the final outcome of a pre-trade risk evaluation."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    """Immutable outcome container for a pre-trade risk evaluation.

    Guarantees that decisions are fully traceable to a specific policy version
    and execution trace with strict runtime type and semantic validation.
    """
    request_id: str
    status: RiskStatus
    violations: Tuple[RiskViolation, ...]
    policy_version: str
    execution_trace_id: str

    def __post_init__(self) -> None:
        """Enforces strict structural, type, and semantic invariants."""
        if not isinstance(self.status, RiskStatus):
            raise TypeError(f"status must be an instance of RiskStatus, got {type(self.status)}")

        if not isinstance(self.violations, tuple):
            raise TypeError(f"violations must be a tuple, got {type(self.violations)}")

        for violation in self.violations:
            if not isinstance(violation, RiskViolation):
                raise TypeError(f"All items in violations must be RiskViolation instances, got {type(violation)}")

        if not self.request_id.strip():
            raise ValueError("RiskCheckResult request_id cannot be empty")
        if not self.policy_version.strip():
            raise ValueError("RiskCheckResult policy_version cannot be empty")
        if not self.execution_trace_id.strip():
            raise ValueError("RiskCheckResult execution_trace_id cannot be empty")

        # Semantic Invariants
        if self.status == RiskStatus.REJECTED and not self.violations:
            raise ValueError("REJECTED status must contain at least one risk violation")
        if self.status == RiskStatus.APPROVED and self.violations:
            raise ValueError("APPROVED status cannot contain risk violations")
