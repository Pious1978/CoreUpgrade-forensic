from typing import Dict, Any, List, Optional
from core.policy_loader import PolicyLoader
from core.logger import get_logger

logger = get_logger("decision_engine")


class DecisionEngine:
    """
    Institutional decision intelligence layer governed by externalized policy configurations.
    """

    def __init__(self, policy_loader: Optional[PolicyLoader] = None):
        self.policy = (policy_loader or PolicyLoader()).get()

    def decide(self, compliance_eval: Dict[str, Any], risk_eval: Dict[str, Any]) -> Dict[str, Any]:
        compliance_score = compliance_eval.get("compliance_score", 0.0)
        risk_score = risk_eval.get("risk_score", 100.0)
        critical_defects = compliance_eval.get("critical_defects", 0)

        approval_cfg = self.policy.get("approval", {"minimum_compliance_score": 90, "maximum_risk_score": 20})
        conditional_cfg = self.policy.get("conditional", {"minimum_compliance_score": 80, "maximum_risk_score": 50})
        rejection_cfg = self.policy.get("rejection", {"critical_findings_allowed": 0})

        min_approval_comp = approval_cfg.get("minimum_compliance_score", 90)
        max_approval_risk = approval_cfg.get("maximum_risk_score", 20)
        min_cond_comp = conditional_cfg.get("minimum_compliance_score", 80)
        max_cond_risk = conditional_cfg.get("maximum_risk_score", 50)
        max_critical = rejection_cfg.get("critical_findings_allowed", 0)

        required_actions: List[str] = []
        blocked_controls: List[str] = []

        controls = compliance_eval.get("controls", {})
        for cat, audits in controls.items():
            for audit in audits:
                if audit.get("status") == "FAIL":
                    blocked_controls.append(f"{cat}:{audit.get('audit_id')}")

        if critical_defects > max_critical:
            decision = "REJECTED"
            confidence = 0.98
            summary = f"Critical defects ({critical_defects}) exceed policy limit ({max_critical}). Execution rejected."
        elif compliance_score >= min_approval_comp and risk_score <= max_approval_risk:
            decision = "APPROVED"
            confidence = 0.95
            summary = "Compliance score and risk exposure satisfy absolute approval thresholds."
        elif compliance_score >= min_cond_comp and risk_score <= max_cond_risk:
            decision = "CONDITIONAL_APPROVAL"
            confidence = 0.85
            summary = "Metrics fall within conditional policy boundaries; deployment permitted under oversight."
            required_actions.append("Review warning findings and non-conformances within 48 operational hours.")
        else:
            decision = "REJECTED"
            confidence = 0.92
            summary = "Compliance score or risk exposure violates institutional policy rules."

        if blocked_controls and decision == "REJECTED":
            required_actions.extend([f"Mitigate failed control: {ctrl}" for ctrl in blocked_controls])

        return {
            "decision": decision,
            "confidence": confidence,
            "required_actions": required_actions,
            "blocked_controls": blocked_controls,
            "executive_summary": summary,
            "metrics": {
                "compliance_score": compliance_score,
                "risk_score": risk_score
            }
        }
