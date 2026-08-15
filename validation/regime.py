import numpy as np

class RegimeDetector:
    """Detects prevailing market regimes based on volatility and trend."""

    @staticmethod
    def detect_regime(market_prices: np.ndarray) -> str:
        if len(market_prices) < 20:
            return "SIDEWAYS"
        
        returns = np.diff(market_prices) / market_prices[:-1]
        volatility = np.std(returns) * np.sqrt(252)
        trend = (market_prices[-1] - market_prices[0]) / market_prices[0]

        if volatility > 0.25:
            return "HIGH_VOLATILITY"
        elif trend > 0.05:
            return "BULL"
        elif trend < -0.05:
            return "BEAR"
        else:
            return "SIDEWAYS"
