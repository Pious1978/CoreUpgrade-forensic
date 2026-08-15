import numpy as np

class RiskMetrics:
    """Quantitative risk calculations for volatility and Value at Risk (VaR)."""

    @staticmethod
    def portfolio_volatility(weights: np.ndarray, covariance: np.ndarray) -> float:
        """Calculates annualized portfolio volatility: sqrt(w^T * Sigma * w)."""
        return float(np.sqrt(np.dot(weights.T, np.dot(covariance, weights))))

    @staticmethod
    def historical_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculates historical Value at Risk (VaR) at the specified confidence level."""
        percentile = (1.0 - confidence) * 100.0
        return float(abs(np.percentile(returns, percentile)))
