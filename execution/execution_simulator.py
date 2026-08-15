import numpy as np
from typing import Dict, Any
from execution.order import Order
from execution.child_order import ChildOrderEngine
from execution.vwap import VWAPExecution

class ExecutionSimulator:
    """
    Institutional execution simulator modeling arrival price, market impact, 
    fill schedules, and implementation shortfall.
    """
    
    def __init__(self, arrival_price: float, spread: float, volatility: float, adv_shares: float):
        self.arrival_price = arrival_price
        self.spread = spread
        self.volatility = volatility
        self.adv = adv_shares
        self.child_engine = ChildOrderEngine()
        self.vwap_engine = VWAPExecution()

    def simulate_execution(self, order: Order, execution_style: str = "VWAP") -> Dict[str, Any]:
        child_quantities = self.vwap_engine.generate_schedule(order.quantity) if execution_style == "VWAP" else [order.quantity]
        
        fills = []
        total_filled = 0.0
        weighted_price_sum = 0.0

        for i, qty in enumerate(child_quantities):
            participation = qty / max(self.adv, 1.0)
            # Square-root impact model + half spread
            impact = 0.5 * self.volatility * np.sqrt(participation) + (self.spread * 0.5)
            fill_price = self.arrival_price * (1.0 + impact if order.side == "BUY" else 1.0 - impact)
            
            fills.append({"slice": i + 1, "qty": qty, "price": round(fill_price, 2)})
            total_filled += qty
            weighted_price_sum += fill_price * qty

        avg_fill_price = weighted_price_sum / total_filled if total_filled > 0 else self.arrival_price
        
        # Implementation shortfall in basis points (bps)
        if order.side == "BUY":
            implementation_shortfall = ((avg_fill_price - self.arrival_price) / self.arrival_price) * 10000
        else:
            implementation_shortfall = ((self.arrival_price - avg_fill_price) / self.arrival_price) * 10000

        return {
            "symbol": order.symbol,
            "side": order.side,
            "requested_quantity": order.quantity,
            "filled_quantity": total_filled,
            "arrival_price": self.arrival_price,
            "average_fill_price": round(avg_fill_price, 2),
            "implementation_shortfall_bps": round(implementation_shortfall, 2),
            "execution_style": execution_style,
            "fills_detail": fills
        }
