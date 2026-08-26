from typing import Any
from ..base_promoter import BasePromotionService
from ..context import PromotionContext
from ..guards.capability_guard import CapabilityGuard
from ..guards.lineage_dag_guard import LineageDagGuard
from ..graph import promotion
from ..policies.research_policy import ResearchPromotionPolicy
from contracts.lifecycle_transition_service import LifecycleTransitionService
from ..exceptions import PolicyViolationError, LifecycleTransitionError

class ResearchSignalContract: CONTRACT_TYPE = "ResearchSignalContract"
class PortfolioIntentContract: CONTRACT_TYPE = "PortfolioIntentContract"

@promotion(source=ResearchSignalContract, target=PortfolioIntentContract)
class ResearchToPortfolioPromoter(BasePromotionService):
    """Concrete promoter coordinating ResearchSignalContract -> PortfolioIntentContract promotion via Policy."""

    def __init__(self) -> None:
        super().__init__()
        self.policy = ResearchPromotionPolicy(min_confidence=0.6)

    def validate_source(self, source: Any, context: PromotionContext) -> None:
        LineageDagGuard.verify(source, ResearchSignalContract)

    def validate_capabilities(self, source: Any, context: PromotionContext) -> None:
        CapabilityGuard.require(source, "PROMOTE_TO_PORTFOLIO", context)

    def evaluate_policy(self, source: Any, context: PromotionContext) -> Any:
        min_threshold = context.extra.get("min_confidence_threshold", 0.6) if hasattr(context, "extra") else 0.6
        self.policy.min_confidence = min_threshold
        
        policy_result = self.policy.evaluate(source, context)
        if not policy_result.passed:
            raise PolicyViolationError(f"Research promotion policy failed: {policy_result.reason}")
        return policy_result

    def create_decision(self, source: Any, policy_result: Any, context: PromotionContext) -> Any:
        signal_id = getattr(source, "signal_id", "unknown")
        decision_payload = {
            "contract_type": "PromotionDecisionContract",
            "decision_id": f"decision-{signal_id}",
            "rule_version": "v2.1.0",
            "rule_set": "RESEARCH_CONFIDENCE_GATE",
            "evaluation_scores": policy_result.scores,
            "passed_rules": list(policy_result.passed_rules),
            "failed_rules": list(policy_result.failed_rules),
            "decision_reason": policy_result.reason,
            "approver": context.actor,
            "status": "APPROVED"
        }
        return decision_payload

    def create_target(self, source: Any, decision: Any, context: PromotionContext) -> Any:
        signal_id = getattr(source, "signal_id", "unknown")
        intent_payload = {
            "contract_type": "PortfolioIntentContract",
            "intent_id": f"intent-{signal_id}",
            "source_signal_id": signal_id,
            "symbol": getattr(source, "symbol", "UNKNOWN"),
            "target_weight": getattr(source, "suggested_weight", 0.0),
            "trust_level": "GOVERNANCE_CERTIFIED",
            "lifecycle_state": "DRAFT"
        }
        return intent_payload

    def validate_target(self, target: Any, context: PromotionContext) -> None:
        weight = getattr(target, "target_weight", target.get("target_weight", 0.0))
        if weight <= 0.0:
            raise LifecycleTransitionError("Generated PortfolioIntentContract has invalid zero or negative weight.")

    def transition_source(self, source: Any, context: PromotionContext) -> Any:
        return LifecycleTransitionService.promote(
            contract=source,
            target_state="PORTFOLIO_ELIGIBLE",
            target_trust="GOVERNANCE_CERTIFIED",
            actor=context.actor,
            reason="Promoted to PortfolioIntentContract."
        )

    def create_audit(self, source: Any, target: Any, decision: Any, context: PromotionContext) -> Any:
        return {
            "contract_type": "PromotionAuditContract",
            "source_id": getattr(source, "signal_id", None),
            "target_id": target.get("intent_id") if isinstance(target, dict) else getattr(target, "intent_id", None),
            "trace_id": str(context.trace_id),
            "verification_status": "VERIFIED"
        }
