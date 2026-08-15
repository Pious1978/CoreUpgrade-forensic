from dataclasses import dataclass


@dataclass(frozen=True)
class ControlDefinition:
    """
    Immutable governance control definition containing comprehensive ownership
    and remediation telemetry.
    """
    control_id: str
    category: str
    weight: float
    mandatory: bool
    owner_team: str
    owner_role: str
    compliance_threshold: float
    impact_score: float
    failure_multiplier: float
    remediation_sla_hours: int
    description: str
    version: str = "1.0"
