# execution/oms/order_state_machine.py
from enum import Enum
from typing import Dict, Set

class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

VALID_TRANSITIONS: Dict[OrderState, Set[OrderState]] = {
    OrderState.CREATED: {
        OrderState.SUBMITTED
    },
    OrderState.SUBMITTED: {
        OrderState.ACKNOWLEDGED,
        OrderState.REJECTED
    },
    OrderState.ACKNOWLEDGED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.FILLED,
        OrderState.CANCEL_PENDING
    },
    OrderState.CANCEL_PENDING: {
        OrderState.CANCELLED,
        OrderState.FILLED
    },
    OrderState.FILLED: set(),
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set()
}

class OrderStateMachine:
    """
    Enforces closed-lifecycle transitions for order states.
    Prevents illegal state jumps (e.g., FILLED -> CANCELLED).
    """
    @staticmethod
    def validate_transition(current_state: OrderState, target_state: OrderState) -> bool:
        allowed = VALID_TRANSITIONS.get(current_state, set())
        return target_state in allowed

    @staticmethod
    def transition(current_state: OrderState, target_state: OrderState) -> OrderState:
        if not OrderStateMachine.validate_transition(current_state, target_state):
            raise ValueError(
                f"Illegal Order State Transition: Cannot transition from {current_state} to {target_state}."
            )
        return target_state
