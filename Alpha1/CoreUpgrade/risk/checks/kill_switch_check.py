from decimal import Decimal
from typing import Optional

from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_violation import RiskViolation
from risk.policies.risk_policy import RiskPolicy


def check_kill_switch(request: RiskCheckRequest, policy: RiskPolicy) -> Optional[RiskViolation]:
    """Validates whether the global risk kill switch is engaged."""
    if policy.kill_switch_enabled:
        return RiskViolation(
            code="KILL_SWITCH_ACTIVE",
            severity="CRITICAL",
            message="Trading is globally halted via active risk kill switch.",
            metric_value=Decimal("1"),
            limit_value=Decimal("0")
        )
    return None
