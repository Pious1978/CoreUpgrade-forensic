from core.audit_config import config

class GovernanceEngine:
    """Evaluates declarative governance and compliance policies through structured condition predicates."""

    @staticmethod
    def evaluate(scoring_result: dict, results: list, telemetry_metrics: dict = None) -> dict:
        score = scoring_result["final_score"]
        critical_count = sum(cat["critical"] for cat in scoring_result["category_breakdowns"].values())
        risk_score = scoring_result["category_breakdowns"].get("risk", {}).get("score", 100.0)
        audit_incomplete = any(met.exceptions or met.timeouts > 0 for met in telemetry_metrics.values()) if telemetry_metrics else False

        ctx = {
            "score": score,
            "critical_findings": critical_count,
            "risk_score": risk_score,
            "database_unavailable": audit_incomplete
        }

        actions = set()
        for rule in config.governance.rules:
            if GovernanceEngine._eval_condition(rule.get("condition"), ctx):
                actions.add(rule.get("action"))

        non_compliant = "non_compliant" in actions or score < config.scoring.pass_threshold
        block_release = "block_release" in actions or critical_count > 0
        escalate = "escalate" in actions or risk_score < 60.0

        health = "HEALTHY"
        if critical_count > 0 or score < 70.0:
            health = "AT_RISK"
        elif score < config.scoring.pass_threshold or audit_incomplete:
            health = "WARNING"

        deployment = "APPROVED"
        if block_release or non_compliant:
            deployment = "BLOCKED"
        elif health == "WARNING":
            deployment = "ALLOW_WITH_WARNINGS"

        executive_summary = (
            f"Governance evaluation: Health status [{health}]. Final Score: {score}/{config.scoring.max_score}. "
            f"Deployment Posture: {deployment}. Triggered actions: {list(actions)}."
        )

        return {
            "health": health,
            "compliance": "NON_COMPLIANT" if non_compliant else "COMPLIANT",
            "deployment": deployment,
            "release_approval": not block_release and not non_compliant,
            "production_readiness": "READY" if health == "HEALTHY" else ("CONDITIONAL" if health == "WARNING" else "NOT_READY"),
            "escalation": escalate,
            "audit_incomplete": audit_incomplete,
            "triggered_actions": list(actions),
            "executive_summary": executive_summary
        }

    @staticmethod
    def _eval_condition(condition: str, ctx: dict) -> bool:
        try:
            parts = condition.split()
            if len(parts) == 3:
                left, op, right = parts[0], parts[1], parts[2]
                val = ctx.get(left, 0)
                target = float(right) if '.' in right or right.isdigit() else right
                
                if op == "<": return val < target
                if op == "<=": return val <= target
                if op == ">": return val > target
                if op == ">=": return val >= target
                if op == "==": return val == target
        except Exception:
            pass
        return False
