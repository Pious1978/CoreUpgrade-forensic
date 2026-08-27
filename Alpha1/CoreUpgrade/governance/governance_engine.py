from typing import Dict, Any, List

class GovernanceEngine:
    """
    Central governance authority aggregating policy, compliance, and kill switch assessments 
    into a definitive approval verdict.
    """
    
    def __init__(self, policy_engine: PolicyEngine, compliance_engine: ComplianceEngine, kill_switch: KillSwitch):
        self.policy = policy_engine
        self.compliance = compliance_engine
        self.kill_switch = kill_switch

    def evaluate_governance(self, portfolio_state: Dict[str, Any], weights: Dict[str, float], cash_pct: float, beta: float, symbols: List[str]) -> Dict[str, Any]:
        # 1. Check Kill Switch first (Absolute Priority)
        ks_triggered, ks_action, ks_reason = self.kill_switch.evaluate_triggers(portfolio_state)
        if ks_triggered:
            return {
                "decision": "HARD_BLOCK",
                "action": ks_action,
                "reason": f"KILL SWITCH TRIGGERED: {ks_reason}",
                "violations": [{"source": "KILL_SWITCH", "message": ks_reason}]
            }

        # 2. Check Compliance
        comp_violations = self.compliance.check_compliance(symbols)
        if comp_violations:
            return {
                "decision": "HARD_BLOCK",
                "action": "REJECT_ORDERS",
                "reason": "Compliance violation detected on proposed symbols.",
                "violations": comp_violations
            }

        # 3. Check Policy Rules
        policy_violations = self.policy.evaluate_policies(weights, cash_pct, beta)
        if policy_violations:
            critical_count = sum(1 for v in policy_violations if v.get("severity") == "CRITICAL")
            decision = "HARD_BLOCK" if critical_count > 0 else "SOFT_BLOCK"
            return {
                "decision": decision,
                "action": "REPAIR_OR_REJECT",
                "reason": f"Policy engine reported {len(policy_violations)} active violations.",
                "violations": policy_violations
            }

        return {
            "decision": "PASS",
            "action": "APPROVE_EXECUTION",
            "reason": "All governance, compliance, and policy checks cleared successfully.",
            "violations": []
        }
