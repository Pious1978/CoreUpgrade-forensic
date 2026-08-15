from typing import Any
from .base_promoter import BasePromotionService
from .promotion_context import PromotionContext
from .guards import CapabilityGuard, LineageGuard, LifecycleTransitionService
from .exceptions import BusinessRuleViolationError

class ResearchToPortfolioPromoter(BasePromotionService):
    """Concrete promoter handling ResearchSignalContract -> PortfolioIntentContract promotion."""

    def validate_source(self, source: Any, context: PromotionContext) -> None:
        LineageGuard.verify(source, "ResearchSignalContract")

    def validate_capabilities(self, source: Any, context: PromotionContext) -> None:
        CapabilityGuard.require(source, "PROMOTE_TO_PORTFOLIO", context)

    def validate_business_rules(self, source: Any, context: PromotionContext) -> None:
        confidence = getattr(source, "confidence_score", 0.0)
        min_threshold = context.extra.get("min_confidence_threshold", 0.6)
        if confidence < min_threshold:
            raise BusinessRuleViolationError(
                f"Confidence score {confidence} is below minimum threshold {min_threshold}."
            )

    def validate_lifecycle_eligibility(self, source: Any, context: PromotionContext) -> None:
        state = getattr(source, "lifecycle_state", "ACTIVE")
        if state != "ACTIVE":
            raise LifecycleTransitionError(f"Source contract state '{state}' is ineligible for promotion.")

    def create_decision(self, source: Any, context: PromotionContext) -> Any:
        # Returns immutable decision contract authorizing the creation
        return {
            "contract_type": "PromotionDecisionContract",
            "decision_id": f"decision-{getattr(source, 'signal_id', 'unknown')}",
            "status": "APPROVED",
            "actor": context.actor,
            "justification": "Passed all signal confidence thresholds and desk capabilities."
        }

    def create_target(self, source: Any, decision: Any, context: PromotionContext) -> Any:
        # Returns immutable PortfolioIntentContract instance
        signal_id = getattr(source, "signal_id", "unknown")
        return {
            "contract_type": "PortfolioIntentContract",
            "intent_id": f"intent-{signal_id}",
            "source_signal_id": signal_id,
            "symbol": getattr(source, "symbol", "UNKNOWN"),
            "target_weight": getattr(source, "suggested_weight", 0.0),
            "trust_level": "GOVERNANCE_CERTIFIED",
            "lifecycle_state": "DRAFT"
        }

    def validate_target(self, target: Any, context: PromotionContext) -> None:
        if not target.get("intent_id") or target.get("target_weight", 0.0) <= 0.0:
            raise BusinessRuleViolationError("Generated PortfolioIntentContract failed post-creation validation.")

    def transition_source(self, source: Any, context: PromotionContext) -> Any:
        return LifecycleTransitionService.promote(
            contract=source,
            target_state="PORTFOLIO_ELIGIBLE",
            target_trust="GOVERNANCE_CERTIFIED",
            actor=context.actor,
            reason="Promoted to PortfolioIntent via PromotionEngine."
        )

    def create_audit(self, source: Any, target: Any, decision: Any, context: PromotionContext) -> Any:
        return {
            "contract_type": "PromotionAuditContract",
            "source_id": getattr(source, "signal_id", None),
            "target_id": target.get("intent_id"),
            "decision_id": decision.get("decision_id"),
            "trace_id": str(context.trace_id),
            "verification_status": "VERIFIED"
        }
