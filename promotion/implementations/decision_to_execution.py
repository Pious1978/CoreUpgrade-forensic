from typing import Any
from ..base_promoter import BasePromotionService
from ..promotion_context import PromotionContext
from ..guards.capability_guard import CapabilityGuard
from ..guards.lineage_guard import LineageGuard
from ..services.lifecycle_transition import LifecycleTransitionService
from ..exceptions import BusinessRuleViolationError, LifecycleTransitionError

class DecisionToExecutionPromoter(BasePromotionService):
    """Concrete promoter handling PortfolioDecisionContract -> ExecutionPlanContract promotion."""

    def validate_source(self, source: Any, context: PromotionContext) -> None:
        LineageGuard.verify(source, "PortfolioDecisionContract")

    def validate_capabilities(self, source: Any, context: PromotionContext) -> None:
        CapabilityGuard.require(source, "EXECUTION_PLANNING", context)

    def validate_business_rules(self, source: Any, context: PromotionContext) -> None:
        status = getattr(source, "status", "APPROVED")
        if status != "APPROVED":
            raise BusinessRuleViolationError(f"Cannot execute unapproved PortfolioDecisionContract status: '{status}'.")

    def validate_lifecycle_eligibility(self, source: Any, context: PromotionContext) -> None:
        state = getattr(source, "lifecycle_state", "ACTIVE")
        if state != "ACTIVE":
            raise LifecycleTransitionError(f"PortfolioDecisionContract state '{state}' is ineligible for execution planning.")

    def create_decision(self, source: Any, context: PromotionContext) -> Any:
        decision_class = context.extra.get("ExecutionDecisionRecordClass")
        decision_id = getattr(source, "decision_id", "unknown")
        if decision_class and hasattr(decision_class, "create"):
            return decision_class.create(
                decision_id=f"exec-auth-{decision_id}",
                status="AUTHORIZED",
                actor=context.actor,
                causation_id=context.causation_id
            )
        return {"contract_type": "ExecutionDecisionRecord", "status": "AUTHORIZED"}

    def create_target(self, source: Any, decision: Any, context: PromotionContext) -> Any:
        target_class = context.extra.get("ExecutionPlanContractClass")
        decision_id = getattr(source, "decision_id", "unknown")
        if target_class and hasattr(target_class, "create"):
            return target_class.create(
                plan_id=f"plan-{decision_id}",
                source_decision_id=decision_id,
                symbol=getattr(source, "symbol", "UNKNOWN"),
                target_quantity=getattr(source, "approved_weight", 0.0) * 1000.0, # Scaled sizing conversion
                order_type=context.extra.get("default_order_type", "TWAP"),
                parent_contract_id=getattr(source, "immutable_id", None)
            )
        return {
            "contract_type": "ExecutionPlanContract",
            "plan_id": f"plan-{decision_id}",
            "source_decision_id": decision_id,
            "lifecycle_state": "ROUTING",
            "trust_level": "GOVERNANCE_CERTIFIED"
        }

    def validate_target(self, target: Any, context: PromotionContext) -> None:
        plan_id = getattr(target, "plan_id", target.get("plan_id"))
        if not plan_id:
            raise BusinessRuleViolationError("Generated ExecutionPlanContract lacks a valid plan ID.")

    def transition_source(self, source: Any, context: PromotionContext) -> Any:
        return LifecycleTransitionService.promote(
            contract=source,
            target_state="EXECUTED_PLANNED",
            target_trust="GOVERNANCE_CERTIFIED",
            actor=context.actor,
            reason="Promoted to ExecutionPlanContract."
        )

    def create_audit(self, source: Any, target: Any, decision: Any, context: PromotionContext) -> Any:
        audit_class = context.extra.get("PromotionAuditContractClass")
        if audit_class and hasattr(audit_class, "create"):
            return audit_class.create(
                source_id=getattr(source, "decision_id", None),
                target_id=getattr(target, "plan_id", target.get("plan_id")),
                trace_id=str(context.trace_id),
                verification_status="VERIFIED"
            )
        return {"contract_type": "PromotionAuditContract", "verification_status": "VERIFIED"}
