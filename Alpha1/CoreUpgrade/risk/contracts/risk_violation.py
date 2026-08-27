from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskViolation:
    """Immutable representation of a specific risk policy breach.

    Captures the exact code, metric value, and breaching threshold for auditability.
    """
    code: str
    severity: str
    message: str
    metric_value: Decimal
    limit_value: Decimal

    def __post_init__(self) -> None:
        """Enforces structural invariants on risk violations."""
        if not self.code.strip():
            raise ValueError("RiskViolation code cannot be empty")
        if not self.severity.strip():
            raise ValueError("RiskViolation severity cannot be empty")
        if not self.message.strip():
            raise ValueError("RiskViolation message cannot be empty")
