from dataclasses import dataclass
from typing import Dict, Any, List, Optional

class ControlValidationError(Exception):
    """Raised when a control definition fails validation contracts."""
    pass

@dataclass(frozen=True)
class ValidationRuleResult:
    is_valid: bool
    errors: List[str]

class ControlValidator:
    """Enforces strict structural and business-logic invariants on control definitions."""
    
    @staticmethod
    def validate(control_data: Dict[str, Any]) -> None:
        errors: List[str] = []

        # Weight validation
        weight = control_data.get("weight", 0)
        if not isinstance(weight, (int, float)) or weight <= 0:
            errors.append(f"Control weight must be a positive number, got: {weight}")

        # Threshold validation
        thresholds = control_data.get("threshold", {})
        compliance_thresh = thresholds.get("compliance")
        if compliance_thresh is not None:
            if not (0 <= compliance_thresh <= 100):
                errors.append(f"Compliance threshold must be between 0 and 100, got: {compliance_thresh}")

        # Impact validation
        risk = control_data.get("risk", {})
        impact = risk.get("impact")
        if impact is not None and (not isinstance(impact, (int, float)) or impact <= 0):
            errors.append(f"Risk impact must be a positive value, got: {impact}")

        # SLA validation
        sla = control_data.get("remediation_sla_hours")
        if sla is not None and (not isinstance(sla, (int, float)) or sla < 0):
            errors.append(f"Remediation SLA hours cannot be negative, got: {sla}")

        # Mandatory ownership validation
        is_mandatory = control_data.get("mandatory", False)
        owner = control_data.get("owner_team")
        if is_mandatory and not owner:
            errors.append("Mandatory controls must define an 'owner_team'.")

        if errors:
            control_id = control_data.get("id", "UNKNOWN_CONTROL")
            raise ControlValidationError(f"Validation failed for control '{control_id}': {errors}")
