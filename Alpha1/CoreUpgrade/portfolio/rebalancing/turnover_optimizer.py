from typing import List, Dict, Any

class TurnoverOptimizer:
    """
    Filters out marginal rebalancing trades to suppress unnecessary turnover and slippage friction.
    """
    
    def __init__(self, min_trade_threshold_usd: float = 5000.0):
        self.min_threshold = min_trade_threshold_usd

    def filter_insignificant_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [t for t in trades if t["estimated_value"] >= self.min_threshold]
