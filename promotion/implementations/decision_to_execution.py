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
            raise BusinessRuleViolationError(
                f"Cannot execute unapproved PortfolioDecisionContract status: '{status}'."
            )

    def validate_lifecycle_eligibility(
        self, source: Any, context: PromotionContext
    ) -> None:
        state = getattr(source, "lifecycle_state", "ACTIVE")
        if state != "ACTIVE":
            raise LifecycleTransitionError(
                f"PortfolioDecisionContract state '{state}' is ineligible for execution planning."
            )

    def create_decision(self, source: Any, context: PromotionContext) -> Any:
        decision_class = context.extra.get("ExecutionDecisionRecordClass")
        decision_id = getattr(source, "decision_id", "unknown")

        if decision_class and hasattr(decision_class, "create"):
            return decision_class.create(
                decision_id=f"exec-auth-{decision_id}",
                status="AUTHORIZED",
                actor=context.actor,
                causation_id=context.causation_id,
            )

        return {
            "contract_type": "ExecutionDecisionRecord",
            "status": "AUTHORIZED",
        }

    def create_target(
        self, source: Any, decision: Any, context: PromotionContext
    ) -> Any:
        """
        Construct the canonical contracts.execution.ExecutionPlanContract.

        The repository's live import resolves `contracts.execution` to the
        module `contracts/execution.py`. That contract does not expose a
        create() factory, so construction must use its dataclass constructor.
        """
        from contracts.execution import ExecutionPlanContract

        decision_id = getattr(source, "decision_id", "unknown")

        symbol = getattr(
            source,
            "symbol",
            getattr(source, "instrument_id", "UNKNOWN"),
        )

        approved_weight = getattr(source, "approved_weight", 0.0)

        target_quantity = context.extra.get(
            "target_quantity",
            approved_weight * 1000.0,
        )

        order_type = context.extra.get(
            "default_order_type",
            "TWAP",
        )

        return ExecutionPlanContract(
            contract_type="ExecutionPlanContract",
            domain="EXECUTION_PLANNING",
            trust_level="GOVERNANCE_CERTIFIED",
            lifecycle_state="ROUTING",
            plan_id=f"plan-{decision_id}",
            symbol=symbol,
            target_quantity=float(target_quantity),
            order_type=str(order_type),
            parent_contract_id=getattr(
                source,
                "immutable_id",
                None,
            ),
            root_contract_id=getattr(
                source,
                "root_contract_id",
                None,
            ),
            correlation_id=(
                context.correlation_id
                if context.correlation_id is not None
                else getattr(source, "correlation_id", None)
            ),
            producer="promotion.decision_to_execution",
            metadata={
                "source_decision_id": decision_id,
                "promotion_id": str(context.promotion_id),
                "trace_id": str(context.trace_id),
            },
        )

    def validate_target(self, target: Any, context: PromotionContext) -> None:
        plan_id = (
            getattr(target, "plan_id", None)
            if not isinstance(target, dict)
            else target.get("plan_id")
        )

        if not plan_id:
            raise BusinessRuleViolationError(
                "Generated ExecutionPlanContract lacks a valid plan ID."
            )

    def transition_source(self, source: Any, context: PromotionContext) -> Any:
        return LifecycleTransitionService.promote(
            contract=source,
            target_state="EXECUTED_PLANNED",
            target_trust="GOVERNANCE_CERTIFIED",
            actor=context.actor,
            reason="Promoted to ExecutionPlanContract.",
        )

    def create_audit(
        self,
        source: Any,
        target: Any,
        decision: Any,
        context: PromotionContext,
    ) -> Any:
        audit_class = context.extra.get("PromotionAuditContractClass")

        target_id = (
            getattr(target, "plan_id", None)
            if not isinstance(target, dict)
            else target.get("plan_id")
        )

        if audit_class and hasattr(audit_class, "create"):
            return audit_class.create(
                source_id=getattr(source, "decision_id", None),
                target_id=target_id,
                trace_id=str(context.trace_id),
                verification_status="VERIFIED",
            )

        return {
            "contract_type": "PromotionAuditContract",
            "verification_status": "VERIFIED",
        }