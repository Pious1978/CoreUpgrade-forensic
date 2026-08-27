import time
from typing import Dict, Any

class OrderStateTracker:
    """
    Maintains the strict state machine lifecycle for each order passing through the gateway.
    """
    VALID_STATES = {"CREATED", "VALIDATED", "SUBMITTED", "ACCEPTED", "REJECTED", "PARTIAL", "FILLED", "CANCELLED"}

    def __init__(self):
        self._states: Dict[str, Dict[str, Any]] = {}

    def create_order(self, order_id: str) -> None:
        if order_id in self._states:
            raise ValueError(f"Order {order_id} already exists in state tracker")
        self._states[order_id] = {
            "state": "CREATED",
            "timestamp": int(time.time() * 1000)
        }

    def update_state(self, order_id: str, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid order lifecycle state: {state}")
        
        if order_id not in self._states:
            self.create_order(order_id)
        
        self._states[order_id] = {
            "state": state,
            "timestamp": int(time.time() * 1000)
        }

    def get_state(self, order_id: str) -> str:
        return self._states.get(order_id, {}).get("state", "UNKNOWN")
