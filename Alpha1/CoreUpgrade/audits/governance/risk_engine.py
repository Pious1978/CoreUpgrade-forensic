from typing import Dict, Any, List, Optional
from core.audit_result import AuditRunResult
from core.control_registry import ControlRegistry
from core.logger import get_logger

logger = get_logger("risk_engine")


class RiskEngine:
    """
    Institutional risk calculation engine computing a normalized Risk Exposure Index.
    """

    def __init__(self, result: AuditRunResult, registry: Optional[ControlRegistry] = None):
        self.result = result
        self.registry = registry or ControlRegistry()

    def _estimate_probability(self, score: float, threshold: float) -> float:
        if score < (threshold * 0.6):
            return 1.0
        if score < threshold:
            return 0.5
        return 0.1

    def evaluate_risk(self) -> Dict[str, Any]:
        findings = self.result.findings
        failed_audits = self.result.failed_audits
        scores = self.result.scores

        total_risk_exposure = 0.0
        maximum_exposure = 0.0
        drivers: List[str] = []

        # Compute maximum possible exposure across all registry controls
        for control in self.registry.all().values():
            maximum_exposure += (control.impact_score * control.failure_multiplier * 3.0)

        for audit_id in failed_audits:
            category = self._infer_category(audit_id)
            control = self.registry.get(category)
            impact = control.impact_score if control else 5.0
            multiplier = control.failure_multiplier if control else 2.0
            exposure = impact * 1.0 * multiplier * 3.0
            total_risk_exposure += exposure
            team = control.owner_team if control else "Platform Team"
            drivers.append(f"Blocking infrastructure failure in category '{category}' (Audit: {audit_id}). Owner: {team}.")

        for audit_id, score in scores.items():
            category = self._infer_category(audit_id)
            control = self.registry.get(category)
            impact = control.impact_score if control else 4.0
            threshold = control.compliance_threshold if control else 80.0
            multiplier = control.failure_multiplier if control else 1.0
            
            prob = self._estimate_probability(score, threshold)
            if prob > 0.1:
                exposure = impact * prob * multiplier * 3.0
                total_risk_exposure += exposure

        for finding in findings:
            severity = str(finding.get("severity", "WARNING")).upper()
            category = str(finding.get("category", "research")).lower()
            control = self.registry.get(category)
            impact = control.impact_score if control else 4.0
            multiplier = control.failure_multiplier if control else 1.0
            
            prob = 1.0 if severity == "CRITICAL" else 0.5
            exp_mult = 3.0 if severity == "CRITICAL" else 1.5
            exposure = impact * prob * multiplier * exp_mult
            total_risk_exposure += exposure
            
            if severity == "CRITICAL":
                team = control.owner_team if control else "Platform Team"
                drivers.append(f"Critical defect in '{category}': {finding.get('message', 'Unknown')} (Owner: {team})")

        # Normalize Risk Exposure Index against maximum possible exposure
        if maximum_exposure > 0:
            risk_score = (total_risk_exposure / maximum_exposure) * 100.0
        else:
            risk_score = 0.0
        risk_score = min(risk_score, 100.0)

        if risk_score >= 50.0 or any(str(f.get("severity", "")).upper() == "CRITICAL" for f in findings):
            risk_level = "HIGH"
        elif risk_score >= 20.0 or len(failed_audits) > 0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        if not drivers:
            drivers.append("No active risk drivers identified. All controls performing within acceptable operational risk bounds.")

        return {
            "run_id": self.result.run_id,
            "risk_level": risk_level,
            "risk_score": round(risk_score, 2),
            "drivers": drivers
        }

    def _infer_category(self, audit_id: str) -> str:
        aid = audit_id.lower()
        for cat in self.registry.all().keys():
            if cat in aid:
                return cat
        return "research"
