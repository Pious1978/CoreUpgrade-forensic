class ExecutionCostModel:
    """Estimates spread cost, market impact, and total execution slippage."""

    @staticmethod
    def estimate_costs(order_value: float, order_qty: float, adv: float = 1000000.0, volatility: float = 0.20) -> dict:
        # Spread cost (approx 2 bps = 0.02%)
        spread_cost = order_value * 0.0002
        
        # Participation rate relative to Average Daily Volume (ADV)
        participation_rate = (order_qty / adv) if adv > 0 else 0.01
        
        # Market impact proportional to square root of participation and portfolio volatility
        market_impact_pct = 0.1 * volatility * (participation_rate ** 0.5)
        market_impact_cost = order_value * market_impact_pct
        
        total_slippage = spread_cost + market_impact_cost
        
        return {
            "spread_cost": round(spread_cost, 2),
            "market_impact": round(market_impact_cost, 2),
            "estimated_slippage": round(total_slippage, 2),
            "participation_rate": round(participation_rate * 100, 4)
        }
