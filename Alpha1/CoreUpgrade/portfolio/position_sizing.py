class PositionSizer:
    """
    Institutional position sizing based on volatility risk parity and fixed fractional risk.
    """
    
    def __init__(self, portfolio_capital: float, max_risk_per_trade_pct: float = 0.01):
        self.capital = portfolio_capital
        self.risk_pct = max_risk_per_trade_pct

    def calculate_position(self, entry_price: float, stop_loss_price: float) -> dict:
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 0:
            return {"shares": 0, "allocation_amount": 0.0, "capital_weight": 0.0}
            
        total_risk_capital = self.capital * self.risk_pct
        shares = int(total_risk_capital / risk_per_share)
        allocation_amount = shares * entry_price
        capital_weight = round(allocation_amount / self.capital, 4)
        
        return {
            "shares": shares,
            "allocation_amount": round(allocation_amount, 2),
            "capital_weight": capital_weight
        }
