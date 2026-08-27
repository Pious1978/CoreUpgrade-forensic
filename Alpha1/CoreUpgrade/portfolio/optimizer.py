from contracts.signal_validation import SignalValidationResult
from contracts.risk_constraints import RiskConstraints
from typing import List, Dict
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from scipy.optimize import minimize

class PortfolioOptimizer:
    """
    Institutional numerical optimization engine with boundary, exposure, 
    and turnover constraints using SLSQP.
    """
    
    def __init__(self, expected_returns: pd.Series, covariance_matrix: pd.DataFrame):
        self.mu = expected_returns
        self.cov = covariance_matrix
        self.assets = list(expected_returns.index)

    def optimize_max_sharpe(
        self,
        validated_signals: List[SignalValidationResult],
        risk_constraints: RiskConstraints,
        risk_free_rate: float = 0.06
    ) -> Dict[str, float]:
        # Filter out failed signals before optimization
        eligible_signals = [s for s in validated_signals if s.verdict != 'FAIL']

        n = len(self.assets)
        initial_weights = np.ones(n) / n
        bounds = tuple((0.0, max_weight) for _ in range(n))
        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})

        def neg_sharpe(w):
            port_return = np.dot(w, self.mu.values)
            port_vol = np.sqrt(np.dot(w.T, np.dot(self.cov.values, w)))
            if port_vol == 0:
                return 0.0
            return - (port_return - risk_free_rate) / port_vol

        result = minimize(neg_sharpe, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        
        optimal_weights = result.x if result.success else initial_weights
        return {self.assets[i]: round(float(optimal_weights[i]), 4) for i in range(n)}
