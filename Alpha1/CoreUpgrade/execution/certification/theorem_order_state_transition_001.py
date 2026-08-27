# execution/certification/theorem_order_state_transition_001.py
from execution.oms.order_state_machine import OrderState, OrderStateMachine

class OrderStateTransitionTheorem:
    """
    THEOREM-ORDER-STATE-TRANSITION-001
    Invariant: An order lifecycle may only follow pre-approved, valid state transitions.
    Illegal transitions must be deterministically rejected to protect OMS replay.
    """
    id = "THEOREM-ORDER-STATE-TRANSITION-001"
    version = "1.0.0"

    @classmethod
    def verify(cls, current_state: OrderState, target_state: OrderState) -> dict:
        is_valid = OrderStateMachine.validate_transition(current_state, target_state)
        
        if not is_valid:
            return {
                "certified": False,
                "reason": f"State Transition Violation: Transition from {current_state} to {target_state} is prohibited.",
                "current_state": current_state,
                "target_state": target_state
            }
            
        return {
            "certified": True,
            "reason": None,
            "current_state": current_state,
            "target_state": target_state
        }
