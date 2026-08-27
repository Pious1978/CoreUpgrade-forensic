from decimal import Decimal
from typing import Optional

from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_violation import RiskViolation
from risk.policies.risk_policy import RiskPolicy


def check_position_exposure(request: RiskCheckRequest, policy: RiskPolicy) -> Optional[RiskViolation]:
    """Validates if the resulting position weight exceeds concentration limits."""
    if request.portfolio_value <= Decimal("0"):
        return None

    trade_delta = request.quantity if request.side.value == "BUY" else -request.quantity
    new_position = request.current_position + trade_delta
    new_notional = abs(new_position * request.price)
    position_weight = new_notional / request.portfolio_value

    if position_weight > policy.max_position_weight:
        return RiskViolation(
            code="MAX_POSITION_EXCEEDED",
            severity="HIGH",
            message=f"Resulting position weight {position_weight:.4f} exceeds max allowed weight {policy.max_position_weight}",
            metric_value=position_weight,
            limit_value=policy.max_position_weight
        )
    return None


def check_order_value(request: RiskCheckRequest, policy: RiskPolicy) -> Optional[RiskViolation]:
    """Validates if a single order's notional value exceeds absolute limits."""
    if request.order_notional > policy.max_order_value:
        return RiskViolation(
            code="MAX_ORDER_VALUE_EXCEEDED",
            severity="MEDIUM",
            message=f"Order notional {request.order_notional} exceeds max order value limit {policy.max_order_value}",
            metric_value=request.order_notional,
            limit_value=policy.max_order_value
        )
    return None
