# execution/certification/theorem_order_authorization_001.py
from decimal import Decimal
from typing import Tuple
from execution.contracts.execution_intent import ExecutionIntent
from execution.contracts.order_contract import OrderIntent

class OrderAuthorizationTheorem:
    """
    THEOREM-ORDER-AUTHORIZATION-001

    Invariant:
    Child OrderIntent quantities must exactly reconstruct
    the authorized parent ExecutionIntent delta, preserving directional consistency (side).

    OMS may slice.
    OMS may not create exposure or invert market direction.
    """

    id = "THEOREM-ORDER-AUTHORIZATION-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        intent: ExecutionIntent,
        orders: Tuple[OrderIntent, ...]
    ) -> dict:

        if not orders:
            return {
                "certified": False,
                "reason": "No child orders generated for execution intent."
            }

        total_quantity = sum(
            (
                order.quantity
                for order in orders
            ),
            Decimal("0")
        )

        expected_quantity = abs(intent.delta_quantity)
        
        # Enforce strict directional consistency (Positive delta = BUY, Negative delta = SELL)
        required_side = "BUY" if intent.delta_quantity > 0 else "SELL"

        # Validate parent linkage, instrument match, and side alignment
        for order in orders:
            if order.intent_id != intent.intent_id:
                return {
                    "certified": False,
                    "reason": (
                        f"Order {order.order_id} "
                        "does not belong to parent ExecutionIntent."
                    )
                }

            if order.instrument_id != intent.instrument_id:
                return {
                    "certified": False,
                    "reason": (
                        "Child order instrument mismatch."
                    )
                }

            if order.side != required_side:
                return {
                    "certified": False,
                    "reason": (
                        f"Order directional inversion failure: Order {order.order_id} has side {order.side}, "
                        f"but parent ExecutionIntent requires {required_side} (delta: {intent.delta_quantity})."
                    )
                }

        if total_quantity != expected_quantity:
            return {
                "certified": False,
                "reason": (
                    "Order authorization failure: "
                    "child quantities do not equal parent execution delta."
                ),
                "expected_quantity": expected_quantity,
                "observed_quantity": total_quantity
            }

        return {
            "certified": True,
            "reason": None
        }
