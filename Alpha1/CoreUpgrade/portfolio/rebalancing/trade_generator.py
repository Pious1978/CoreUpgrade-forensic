from typing import Dict, List, Any

class TradeGenerator:
    """
    Pure translation layer converting current vs target weight matrices into discrete trade instructions.
    """
    
    def __init__(self, portfolio_nav: float, current_prices: Dict[str, float]):
        self.nav = portfolio_nav
        self.prices = current_prices

    def generate_trades(self, current_weights: Dict[str, float], target_weights: Dict[str, float]) -> List[Dict[str, Any]]:
        trades = []
        all_symbols = set(current_weights.keys()).union(set(target_weights.keys()))
        
        for sym in all_symbols:
            c_w = current_weights.get(sym, 0.0)
            t_w = target_weights.get(sym, 0.0)
            diff_w = t_w - c_w
            
            if abs(diff_w) < 0.001:  # Suppress dust adjustments
                continue
                
            price = self.prices.get(sym, 100.0)
            dollar_diff = diff_w * self.nav
            shares = abs(dollar_diff) / price
            side = "BUY" if diff_w > 0 else "SELL"
            
            trades.append({
                "symbol": sym,
                "side": side,
                "quantity": round(shares, 2),
                "estimated_value": round(abs(dollar_diff), 2),
                "weight_change": round(diff_w, 4)
            })
        return trades
