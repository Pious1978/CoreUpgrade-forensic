import numpy as np
import pandas as pd
from typing import Dict, Any, List
from portfolio.covariance_engine import CovarianceEngine

class PortfolioRiskEngine:
    """
    Evaluates portfolio-wide risk shifts, Marginal VaR, and exact historical 
    Expected Shortfall (CVaR) from return distribution tails.
    """
    
    def __init__(self, price_history: pd.DataFrame, current_weights: Dict[str, float], portfolio_capital: float):
        self.prices = price_history
        self.cov_engine = CovarianceEngine(price_history)
        self.cov_matrix = self.cov_engine.compute_ledoit_wolf_covariance()
        self.weights_dict = current_weights
        self.capital = portfolio_capital
        self.returns = price_history.pct_change().dropna()

    def _get_weight_vector(self, assets: List[str], weights_map: Dict[str, float]) -> np.ndarray:
        return np.array([weights_map.get(asset, 0.0) for asset in assets])

    def _calculate_historical_es(self, weights: np.ndarray, confidence_level: float = 0.95) -> float:
        portfolio_returns = np.dot(self.returns.values, weights)
        if len(portfolio_returns) == 0:
            return 0.0
        var_threshold = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
        tail_losses = portfolio_returns[portfolio_returns <= var_threshold]
        expected_shortfall = np.mean(tail_losses) if len(tail_losses) > 0 else var_threshold
        return abs(expected_shortfall * self.capital * np.sqrt(252))

    def evaluate_trade_impact(self, candidate_symbol: str, candidate_weight: float, confidence_level: float = 0.95) -> Dict[str, Any]:
        assets = list(self.cov_matrix.index)
        if candidate_symbol not in assets:
            return {"status": "REJECTED", "reason": "Candidate symbol missing from price history universe."}

        curr_weights = self._get_weight_vector(assets, self.weights_dict)
        curr_var = self.cov_engine.get_portfolio_variance(curr_weights, self.cov_matrix)
        curr_vol = np.sqrt(curr_var)
        curr_es = self._calculate_historical_es(curr_weights, confidence_level)

        # Corrected: Build proposed weights using the proposed dictionary, not self.weights_dict
        proposed_weights_dict = self.weights_dict.copy()
        proposed_weights_dict[candidate_symbol] = proposed_weights_dict.get(candidate_symbol, 0.0) + candidate_weight
        prop_weights = self._get_weight_vector(assets, proposed_weights_dict)
        
        prop_var = self.cov_engine.get_portfolio_variance(prop_weights, self.cov_matrix)
        prop_vol = np.sqrt(prop_var)
        prop_es = self._calculate_historical_es(prop_weights, confidence_level)

        z_score = 1.645 if confidence_level == 0.95 else 2.33
        curr_va_r = curr_vol * z_score * np.sqrt(1/252) * self.capital
        prop_va_r = prop_vol * z_score * np.sqrt(1/252) * self.capital

        portfolio_std = prop_vol
        cov_vector = self.cov_matrix.loc[candidate_symbol].values / 252 # Daily scale for marginal risk
        marginal_risk = np.dot(prop_weights, cov_vector) / portfolio_std if portfolio_std > 0 else 0.0

        risk_delta_pct = ((prop_vol - curr_vol) / curr_vol) * 100 if curr_vol > 0 else 0.0

        return {
            "candidate": candidate_symbol,
            "approved": risk_delta_pct <= 15.0,
            "metrics_before": {
                "annualized_volatility": round(curr_vol * 100, 2),
                "var_95": round(curr_va_r, 2),
                "expected_shortfall": round(curr_es, 2)
            },
            "metrics_after": {
                "annualized_volatility": round(prop_vol * 100, 2),
                "var_95": round(prop_va_r, 2),
                "expected_shortfall": round(prop_es, 2)
            },
            "risk_delta_percent": round(risk_delta_pct, 2),
            "marginal_risk_contribution": round(marginal_risk, 4)
        }
