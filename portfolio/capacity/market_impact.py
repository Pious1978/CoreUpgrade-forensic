import numpy as np

class MarketImpactModel:
    """Estimates square-root permanent and temporary market impact."""
    
    def calculate_impact(self, order_shares: float, adv_shares: float, volatility: float, spread: float) -> float:
        if adv_shares <= 0:
            return 1.0
        
        participation = order_shares / adv_shares
        # Square-root impact formula: Impact = alpha * volatility * sqrt(participation) + spread component
        impact = 0.5 * volatility * np.sqrt(max(0.0, participation)) + (spread * 0.5)
        return float(round(impact, 4))
