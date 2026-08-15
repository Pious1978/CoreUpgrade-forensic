from typing import Any
from ..base_promoter import BasePromotionService
from ..promotion_context import PromotionContext
from ..guards.capability_guard import CapabilityGuard
from ..guards.lineage_guard import LineageGuard
from ..services.lifecycle_transition import LifecycleTransitionService
from ..exceptions import BusinessRuleViolationError, LifecycleTransitionError

class ExecutionToResultPromoter(BasePromotionService):
    """Concrete promoter handling ExecutionPlanContract -> ExecutionResultContract promotion."""

    def validate_source(self, source: Any, context: PromotionContext) -> None:
        LineageGuard.verify(source, "ExecutionPlanContract")

    def validate_capabilities(self, source: Any, context: PromotionContext) -> None:
        CapabilityGuard.require(source, "BROKER_EXECUTION", context)

    def validate_business_rules(self, source: Any, context: PromotionContext) -> None:
        fill_price = context.extra.get("fill_price", 0.0)
        if fill_price < 0.0:
            raise BusinessRuleViolationError(f"Invalid execution fill price: {fill_price}.")

    def validate_lifecycle_eligibility(self, source: Any, context: PromotionContext) -> None:
        state = getattr(source, "lifecycle_state", "ROUTING")
        if state not in ("ROUTING", "ACTIVE"):
            raise LifecycleTransitionError(f"ExecutionPlanContract state '{state}' is ineligible for result finalization.")

    def create_decision(self, source: Any, context: PromotionContext) -> Any:
        decision_class = context.extra.get("ReconciliationDecisionRecordClass")
        plan_id = getattr(source, "plan_id", "unknown")
        if decision_class and hasattr(decision_class, "create"):
            return decision_class.create(
                decision_id=f"recon-{plan_id}",
                status="RECONCILED",
                actor=context.actor,
                causation_id=context.causation_id
            )
        return {"contract_type": "ReconciliationDecisionRecord", "status": "RECONCILED"}

    def create_target(self, source: Any, decision: Any, context: PromotionContext) -> Any:
        target_class = context.extra.get("ExecutionResultContractClass")
        plan_id = getattr(source, "plan_id", "unknown")
        if target_class and hasattr(target_class, "create"):
            return target_class.create(
                result_id=f"result-{plan_id}",
                source_plan_id=plan_id,
                executed_quantity=context.extra.get("executed_quantity", 1000.0),
                average_fill_price=context.extra.get("fill_price", 100.0),
                venue=context.extra.get("execution_venue", "PRIMARY_EXCHANGE"),
                parent_contract_id=getattr(source, "immutable_id", None)
            )
        return {
            "contract_type": "ExecutionResultContract",
            "result_id": f"result-{plan_id}",
            "source_plan_id": plan_id,
            "lifecycle_state": "SETTLED",
            "trust_level": "GOVERNANCE_CERTIFIED"
        }

    def validate_target(self, target: Any, context: PromotionContext) -> None:
        result_id = getattr(target, "result_id", target.get("result_id"))
        if not result_id:
            raise BusinessRuleViolationError("Generated ExecutionResultContract lacks a valid result ID.")

    def transition_source(self, source: Any, context: PromotionContext) -> Any:
        return LifecycleTransitionService.promote(
            contract=source,
            target_state="SETTLED",
            target_trust="GOVERNANCE_CERTIFIED",
            actor=context.actor,
            reason="Promoted to ExecutionResultContract via broker fill reconciliation."
        )

    def create_audit(self, source: Any, target: Any, decision: Any, context: PromotionContext) -> Any:
        audit_class = context.extra.get("PromotionAuditContractClass")
        if audit_class and hasattr(audit_class, "create"):
            return audit_class.create(
                source_id=getattr(source, "plan_id", None),
                target_id=getattr(target, "result_id", target.get("result_id")),
                trace_id=str(context.trace_id),
                verification_status="VERIFIED"
            )
        return {"contract_type": "PromotionAuditContract", "verification_status": "VERIFIED"}
