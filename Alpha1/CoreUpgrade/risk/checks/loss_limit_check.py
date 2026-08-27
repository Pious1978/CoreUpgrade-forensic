from decimal import Decimal
from typing import Optional

from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_violation import RiskViolation
from risk.policies.risk_policy import RiskPolicy


def check_loss_limits(request: RiskCheckRequest, policy: RiskPolicy) -> Optional[RiskViolation]:
    """Validates if daily portfolio losses exceed the configured maximum threshold."""
    if request.portfolio_value <= Decimal("0"):
        return None

    # Calculate negative daily PnL fraction as a positive magnitude
    daily_loss_fraction = -request.daily_pnl / request.portfolio_value if request.daily_pnl < Decimal("0") else Decimal("0")

    if daily_loss_fraction > policy.max_daily_loss:
        return RiskViolation(
            code="DAILY_LOSS_LIMIT_BREACHED",
            severity="HIGH",
            message=f"Daily loss fraction {daily_loss_fraction:.4f} breaches maximum limit {policy.max_daily_loss}",
            metric_value=daily_loss_fraction,
            limit_value=policy.max_daily_loss
        )
    return None
