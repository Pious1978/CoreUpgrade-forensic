from typing import Mapping, Any, Dict, List, Optional
from core.audit_result import AuditRunResult
from core.control_registry import ControlRegistry
from core.logger import get_logger

logger = get_logger("compliance_matrix")


class ComplianceMatrix:
    """
    Governance intelligence module implementing continuous weighted compliance scoring.
    """

    def __init__(self, result: AuditRunResult, registry: Optional[ControlRegistry] = None):
        self.result = result
        self.registry = registry or ControlRegistry()

    def evaluate(self) -> Dict[str, Any]:
        scores = self.result.scores
        findings = self.result.findings

        total_weight = 0.0
        earned_weight = 0.0
        controls_heatmap: Dict[str, List[Dict[str, Any]]] = {}

        for audit_id, score in scores.items():
            category = self._infer_category(audit_id)
            control = self.registry.get(category)
            weight = control.weight if control else 2.0
            threshold = control.compliance_threshold if control else 80.0

            total_weight += weight
            
            # Continuous weighted scoring model
            normalized_score = min(score / threshold, 1.0)
            earned_weight += (normalized_score * weight)

            if score >= threshold:
                status = "PASS"
            elif score >= (threshold * 0.8):
                status = "AT_RISK"
            else:
                status = "FAIL"

            controls_heatmap.setdefault(category, []).append({
                "audit_id": audit_id,
                "score": float(score),
                "weight": weight,
                "threshold": threshold,
                "status": status,
                "owner_team": control.owner_team if control else "Platform Team",
                "sla_hours": control.remediation_sla_hours if control else 24
            })

        compliance_percentage = (earned_weight / total_weight * 100.0) if total_weight > 0 else 0.0

        critical_findings = [f for f in findings if str(f.get("severity", "")).upper() == "CRITICAL"]
        warning_findings = [f for f in findings if str(f.get("severity", "")).upper() == "WARNING"]

        if len(critical_findings) > 0:
            posture = "NON-COMPLIANT"
        elif len(warning_findings) > 3 or compliance_percentage < 90.0:
            posture = "CONDITIONAL"
        else:
            posture = "COMPLIANT"

        return {
            "run_id": self.result.run_id,
            "posture": posture,
            "compliance_score": round(compliance_percentage, 2),
            "controls": controls_heatmap,
            "critical_defects": len(critical_findings),
            "warnings": len(warning_findings)
        }

    def _infer_category(self, audit_id: str) -> str:
        aid = audit_id.lower()
        for cat in self.registry.all().keys():
            if cat in aid:
                return cat
        return "research"
