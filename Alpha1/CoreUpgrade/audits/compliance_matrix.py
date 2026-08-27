from typing import Mapping, Any, Dict, Tuple
from core.audit_result import AuditRunResult
from core.logger import get_logger

logger = get_logger("compliance_matrix")


class ComplianceMatrix:
    """
    Governance intelligence module transforming raw audit results into structured
    compliance postures, control scores, and risk distributions.
    """

    def __init__(self, result: AuditRunResult):
        self.result = result

    def evaluate(self) -> Dict[str, Any]:
        """Calculates multi-dimensional control compliance and risk metrics."""
        findings = self.result.findings
        scores = self.result.scores

        total_controls = len(scores) if scores else 1
        passed_controls = sum(1 for s in scores.values() if s >= 80.0)
        compliance_percentage = (passed_controls / total_controls) * 100.0

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
            "total_controls_evaluated": total_controls,
            "passed_controls": passed_controls,
            "critical_defects": len(critical_findings),
            "warnings": len(warning_findings),
            "category_breakdown": self._aggregate_categories(findings)
        }

    def _aggregate_categories(self, findings: Tuple[Mapping[str, Any], ...]) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        for finding in findings:
            cat = str(finding.get("category", "general")).lower()
            breakdown[cat] = breakdown.get(cat, 0) + 1
        return breakdown
