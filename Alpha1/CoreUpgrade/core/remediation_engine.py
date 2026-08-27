from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any
from core.control_definition import ControlDefinition

class RemediationError(Exception):
    """Raised when remediation workflow creation or evaluation fails."""
    pass

@dataclass(frozen=True)
class RemediationTask:
    """Immutable representation of an actionable remediation workflow item."""
    finding_id: str
    control_id: str
    owner_team: str
    severity: str
    created_at: str
    due_at: str
    status: str

class RemediationEngine:
    """Converts normalized governance findings into controlled, SLA-bound remediation workflows."""

    SEVERITY_MULTIPLIER = {
        "CRITICAL": 1.0,
        "HIGH": 0.75,
        "MEDIUM": 0.5,
        "LOW": 0.25
    }

    @staticmethod
    def calculate_due_date(created_at: datetime, sla_hours: int) -> str:
        """Calculates the absolute deadline based on creation time and control SLA hours."""
        deadline = created_at + timedelta(hours=sla_hours)
        return deadline.isoformat()

    @classmethod
    def create_task(cls, finding: Dict[str, Any], control: ControlDefinition) -> RemediationTask:
        """
        Evaluates a finding against a control definition to instantiate an actionable remediation task.
        """
        if not control.owner_team:
            raise RemediationError(
                f"Control '{control.id}' lacks a remediation owner team; cannot assign workflow."
            )

        created = datetime.utcnow()
        due = cls.calculate_due_date(created, control.remediation_sla_hours)

        # Handle flexible dictionary keys for finding IDs safely
        finding_id = finding.get("finding_id") or finding.get("id", "UNKNOWN-FINDING")
        severity = finding.get("severity", "MEDIUM").upper()

        if severity not in cls.SEVERITY_MULTIPLIER:
            raise RemediationError(f"Invalid severity level '{severity}' encountered for finding '{finding_id}'.")

        return RemediationTask(
            finding_id=finding_id,
            control_id=control.id,
            owner_team=control.owner_team,
            severity=severity,
            created_at=created.isoformat(),
            due_at=due,
            status="OPEN"
        )
