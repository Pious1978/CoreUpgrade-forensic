from typing import List, Dict, Any

class CashAllocator:
    """
    Rations and scales buy orders when required capital exceeds available portfolio cash.
    """
    
    def allocate_cash(self, trades: List[Dict[str, Any]], available_cash: float) -> List[Dict[str, Any]]:
        buys = [t for t in trades if t["side"] == "BUY"]
        sells = [t for t in trades if t["side"] == "SELL"]
        
        total_buy_value = sum(b["estimated_value"] for b in buys)
        
        if total_buy_value <= available_cash or total_buy_value == 0:
            return trades
            
        scale_factor = available_cash / total_buy_value
        scaled_buys = []
        for b in buys:
            b_scaled = b.copy()
            b_scaled["estimated_value"] = round(b["estimated_value"] * scale_factor, 2)
            b_scaled["quantity"] = round(b["quantity"] * scale_factor, 2)
            scaled_buys.append(b_scaled)
            
        return sells + scaled_buys
