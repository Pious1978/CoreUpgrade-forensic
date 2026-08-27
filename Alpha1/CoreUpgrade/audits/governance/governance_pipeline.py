from typing import Dict, Any
from core.audit_result import AuditRunResult
from audits.governance.compliance_matrix import ComplianceMatrix
from audits.governance.risk_engine import RiskEngine
from audits.governance.decision_engine import DecisionEngine
from core.logger import get_logger

logger = get_logger("governance_pipeline")


class GovernancePipeline:
    """
    Institutional governance pipeline orchestrating compliance matrices,
    risk engines, and decision scorecards for executive review.
    """

    def __init__(self, result: AuditRunResult):
        self.result = result
        self.matrix = ComplianceMatrix(result)
        self.risk_engine = RiskEngine(result)
        self.decision_engine = DecisionEngine()

    def execute(self) -> Dict[str, Any]:
        """Executes the full governance intelligence evaluation suite."""
        logger.info("Executing governance evaluation pipeline", extra={"run_id": self.result.run_id})

        compliance_evaluation = self.matrix.evaluate()
        risk_evaluation = self.risk_engine.evaluate_risk()
        decision_evaluation = self.decision_engine.decide(compliance_evaluation, risk_evaluation)

        scorecard = {
            "run_id": self.result.run_id,
            "timestamp": self.result.timestamp,
            "run_fingerprint": self.result.run_fingerprint,
            "governance_posture": compliance_evaluation["posture"],
            "compliance_score": compliance_evaluation["compliance_score"],
            "risk_level": risk_evaluation["risk_level"],
            "risk_score": risk_evaluation["risk_score"],
            "decision_verdict": decision_evaluation["decision"],
            "decision_confidence": decision_evaluation["confidence"],
            "executive_summary": decision_evaluation["executive_summary"],
            "required_actions": decision_evaluation["required_actions"],
            "blocked_controls": decision_evaluation["blocked_controls"],
            "controls_heatmap": compliance_evaluation["controls"],
            "risk_drivers": risk_evaluation["drivers"]
        }

        logger.info(
            "Governance evaluation completed",
            extra={
                "run_id": self.result.run_id,
                "posture": scorecard["governance_posture"],
                "risk_level": scorecard["risk_level"],
                "verdict": scorecard["decision_verdict"]
            }
        )

        return scorecard
