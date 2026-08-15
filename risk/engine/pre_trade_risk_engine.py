from typing import Callable, List, Optional, Tuple

from risk.checks.exposure_check import check_order_value, check_position_exposure
from risk.checks.kill_switch_check import check_kill_switch
from risk.checks.loss_limit_check import check_loss_limits
from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_check_result import RiskCheckResult, RiskStatus
from risk.contracts.risk_violation import RiskViolation
from risk.policies.risk_policy import RiskPolicy

# Clean Type Alias for Rule Signatures
RiskCheck = Callable[[RiskCheckRequest, RiskPolicy], Optional[RiskViolation]]


class PreTradeRiskEngine:
    """Orchestrates pre-trade risk evaluations against versioned risk policies.

    Enforces strict engine boundary validations, explicit short-circuit rules,
    and extensible, ordered standard checks.
    """

    # Ordered tuple of standard non-short-circuit check functions
    _STANDARD_CHECKS: Tuple[RiskCheck, ...] = (
        check_loss_limits,
        check_position_exposure,
        check_order_value,
    )

    def __init__(self, policy: RiskPolicy) -> None:
        if not isinstance(policy, RiskPolicy):
            raise TypeError(f"policy must be an instance of RiskPolicy, got {type(policy)}")
        self._policy = policy

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    def evaluate(self, request: RiskCheckRequest, execution_trace_id: str) -> RiskCheckResult:
        """Executes pre-trade risk checks deterministically and returns an immutable result."""
        if not isinstance(request, RiskCheckRequest):
            raise TypeError(f"request must be an instance of RiskCheckRequest, got {type(request)}")

        if not isinstance(execution_trace_id, str) or not execution_trace_id.strip():
            raise ValueError("execution_trace_id must be a non-empty string")

        violations: List[RiskViolation] = []

        # 1. Kill Switch Check (Explicit Exceptional Control Flow Short-Circuit)
        if kill_violation := check_kill_switch(request, self._policy):
            violations.append(kill_violation)
            return RiskCheckResult(
                request_id=request.request_id,
                status=RiskStatus.REJECTED,
                violations=tuple(violations),
                policy_version=self._policy.policy_version,
                execution_trace_id=execution_trace_id,
            )

        # 2. Iterate through ordered standard check functions
        for check in self._STANDARD_CHECKS:
            if violation := check(request, self._policy):
                violations.append(violation)

        status = RiskStatus.REJECTED if violations else RiskStatus.APPROVED

        return RiskCheckResult(
            request_id=request.request_id,
            status=status,
            violations=tuple(violations),
            policy_version=self._policy.policy_version,
            execution_trace_id=execution_trace_id,
        )
