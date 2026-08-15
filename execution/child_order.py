from typing import List, Dict, Any
from execution.order import Order

class ChildOrderEngine:
    """
    Slices institutional parent orders into adaptive child order blocks.
    """
    
    def __init__(self, max_child_size_pct: float = 0.02):
        self.max_child_pct = max_child_size_pct

    def slice_order(self, order: Order, total_adv_shares: float) -> List[Dict[str, Any]]:
        max_shares = total_adv_shares * self.max_child_pct
        remaining = order.quantity
        child_orders = []
        
        slice_id = 1
        while remaining > 0:
            current_qty = min(remaining, max_shares)
            child_orders.append({
                "child_id": f"{order.symbol}-CH-{slice_id}",
                "symbol": order.symbol,
                "side": order.side,
                "quantity": current_qty,
                "urgency": order.urgency
            })
            remaining -= current_qty
            slice_id += 1
            
        return child_orders
