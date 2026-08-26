# execution/translation/execution_to_oms.py

from datetime import datetime
from decimal import Decimal
from typing import Optional

from execution.contracts.execution_intent import ExecutionIntent
from oms.contracts.order_intent import OrderIntentContract, OrderSide, OrderType


def translate_intent_to_oms_order(
    intent: ExecutionIntent,
    *,
    strategy_id: str,
    currency: str,
    order_type: OrderType,
    risk_request_id: str,
    timestamp: datetime,
    price: Optional[Decimal] = None,
) -> OrderIntentContract:
    """
    Boundary 2: Pure transformation converting an authorized ExecutionIntent
    into the canonical OMS OrderIntentContract.

    Translates signed deltas into absolute quantities and directional BUY/SELL
    sides, while binding execution_trace_id directly to intent.intent_hash.

    No OMS submission or broker execution occurs here.
    """
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Timestamp must be timezone-aware.")

    abs_delta = abs(intent.delta_quantity)

    if abs_delta == Decimal("0"):
        raise ValueError(
            "ExecutionIntent delta_quantity must be non-zero."
        )

    side = (
        OrderSide.BUY
        if intent.delta_quantity > Decimal("0")
        else OrderSide.SELL
    )

    return OrderIntentContract(
        intent_id=intent.intent_id,
        portfolio_id=intent.portfolio_id,
        strategy_id=strategy_id,
        symbol=intent.instrument_id,
        side=side,
        order_type=order_type,
        quantity=abs_delta,
        price=price,
        currency=currency,
        risk_request_id=risk_request_id,
        execution_trace_id=intent.intent_hash,
        timestamp=timestamp,
    )