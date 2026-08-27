from dataclasses import dataclass
from typing import Dict, Any
from core.finding import Finding
from core.control_definition import ControlDefinition

class RiskCalculationError(Exception):
    """Raised when risk calculation fails due to invalid parameters or unknown severity."""
    pass

@dataclass(frozen=True)
class RiskScore:
    """Immutable representation of calculated risk exposure for a normalized finding."""
    finding_id: str
    control_id: str
    inherent_risk: float
    normalized_risk: float
    risk_level: str

class RiskEngine:
    """Calculates normalized governance risk exposure based on severity mapping and control weights."""

    SEVERITY_SCORE = {
        "CRITICAL": 100.0,
        "HIGH": 75.0,
        "MEDIUM": 50.0,
        "LOW": 25.0
    }

    @classmethod
    def calculate(cls, finding: Finding, control: ControlDefinition) -> RiskScore:
        """
        Evaluates a finding against a control definition to compute inherent and normalized risk.
        """
        severity_score = cls.SEVERITY_SCORE.get(finding.severity.upper())

        if severity_score is None:
            raise RiskCalculationError(
                f"Unknown severity level '{finding.severity}' encountered for finding '{finding.finding_id}'."
            )

        control_weight = control.weight
        inherent_risk = severity_score * control_weight
        normalized = min(inherent_risk, 100.0)

        if normalized >= 80.0:
            level = "CRITICAL"
        elif normalized >= 60.0:
            level = "HIGH"
        elif normalized >= 40.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        return RiskScore(
            finding_id=finding.finding_id,
            control_id=finding.control_id,
            inherent_risk=inherent_risk,
            normalized_risk=normalized,
            risk_level=level
        )
