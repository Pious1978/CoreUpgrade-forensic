from typing import List

class RecommendationEngine:
    """Translates audit findings and governance states into actionable engineering recommendations."""

    @staticmethod
    def generate(results: list, governance_result: dict, scoring_result: dict) -> List[str]:
        recommendations = []
        
        criticals = [r for r in results if getattr(r, "severity", "").upper() == "CRITICAL"]
        highs = [r for r in results if getattr(r, "severity", "").upper() == "HIGH"]

        if criticals:
            recommendations.append(f"Immediate Remediation Required: Resolve {len(criticals)} CRITICAL audit findings prior to release approval.")
        
        if highs:
            recommendations.append(f"Priority Review: Address {len(highs)} HIGH severity findings to mitigate deployment risks.")

        for cat, breakdown in scoring_result.get("category_breakdowns", {}).items():
            if breakdown["score"] < 80.0:
                recommendations.append(f"Category '{cat.upper()}' score is sub-optimal ({breakdown['score']}/100). Review module findings in this domain.")

        if governance_result.get("escalation"):
            recommendations.append("Executive Escalation Triggered: Risk score dropped below acceptable operational threshold.")

        if governance_result.get("audit_incomplete"):
            recommendations.append("Execution Warning: One or more audit modules experienced timeouts or unhandled exceptions.")

        if not recommendations:
            recommendations.append("All institutional audit checks passed successfully. System is verified healthy and ready for deployment.")

        return recommendations
