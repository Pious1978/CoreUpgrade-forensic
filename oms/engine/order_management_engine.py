from typing import Optional, Tuple

from oms.contracts.order_intent import OrderIntentContract
from oms.models.order import Order
from oms.state_machine.order_state_machine import OrderState
from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_check_result import RiskCheckResult, RiskStatus
from risk.engine.pre_trade_risk_engine import PreTradeRiskEngine


class OrderManagementEngine:
    """Stateless orchestration boundary for intake and risk-validation of trading intents."""

    def __init__(self, risk_engine: PreTradeRiskEngine) -> None:
        self._risk_engine = risk_engine

    def ingest_intent(
        self, intent: OrderIntentContract, risk_request: RiskCheckRequest
    ) -> Tuple[Optional[Order], RiskCheckResult]:
        """Evaluates an intent against operational risk policies. 
        
        Returns a tuple containing the initialized Order (if approved) and the RiskCheckResult.
        """
        if intent.risk_request_id != risk_request.request_id:
            raise ValueError("Intent and RiskRequest identifiers do not match")

        risk_result = self._risk_engine.evaluate(
            request=risk_request, 
            execution_trace_id=intent.execution_trace_id
        )

        if risk_result.status == RiskStatus.REJECTED:
            return None, risk_result

        order = Order(intent=intent)
        order.transition(OrderState.SUBMITTED)

        return order, risk_result
