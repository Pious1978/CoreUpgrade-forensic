from typing import Dict, Any, List

class PortfolioState:
    """
    Maintains the live state of cash, positions, margin, gross/net exposure, 
    and pending institutional orders.
    """
    
    def __init__(self, initial_capital: float, leverage_limit: float = 1.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.leverage_limit = leverage_limit
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.pending_orders: List[Dict[str, Any]] = []

    def update_position(self, symbol: str, shares: float, current_price: float) -> None:
        if shares == 0:
            if symbol in self.positions:
                del self.positions[symbol]
        else:
            market_value = shares * current_price
            self.positions[symbol] = {
                "shares": shares,
                "market_value": market_value,
                "current_price": current_price
            }

    def get_portfolio_metrics(self) -> Dict[str, float]:
        total_market_value = sum(pos["market_value"] for pos in self.positions.values())
        nav = self.cash + total_market_value
        
        gross_exposure = sum(abs(pos["market_value"]) for pos in self.positions.values())
        net_exposure = total_market_value
        
        gross_leverage = gross_exposure / max(self.initial_capital, 1e-4)
        
        return {
            "nav": round(nav, 2),
            "cash": round(self.cash, 2),
            "gross_exposure": round(gross_exposure, 2),
            "net_exposure": round(net_exposure, 2),
            "gross_leverage": round(gross_leverage, 2),
            "active_positions_count": len(self.positions)
        }
