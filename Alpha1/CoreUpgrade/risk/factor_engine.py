import numpy as np
import pandas as pd
from typing import Dict, Any

class FactorEngine:
    """
    Institutional multi-factor risk engine estimating portfolio and asset loadings 
    for Market Beta, Momentum, Volatility, Size, and Value factors.
    """
    
    def __init__(self, asset_returns: pd.DataFrame, factor_benchmarks: pd.DataFrame):
        """
        :param asset_returns: DataFrame of daily asset returns.
        :param factor_benchmarks: DataFrame of daily factor returns (columns: Market, Momentum, Volatility, Size, Value).
        """
        self.asset_returns = asset_returns.sort_index()
        self.factors = factor_benchmarks.sort_index()
        self.aligned_data = pd.concat([self.asset_returns, self.factors], axis=1).dropna()

    def compute_asset_loadings(self, symbol: str) -> Dict[str, float]:
        """Performs Ordinary Least Squares (OLS) multi-factor regression for a single asset."""
        if symbol not in self.asset_returns.columns:
            return {}
            
        y = self.aligned_data[symbol]
        X = self.aligned_data[self.factors.columns]
        X_const = sm_add_constant(X) if 'sm_add_constant' in globals() else pd.DataFrame(X).assign(Intercept=1.0)
        
        try:
            # OLS regression: beta = (X^T X)^-1 X^T y
            XtX_inv = np.linalg.pinv(np.dot(X_const.T, X_const))
            Xty = np.dot(X_const.T, y)
            betas = np.dot(XtX_inv, Xty)
            
            loadings = {col: float(betas[i]) for i, col in enumerate(X_const.columns) if col != 'Intercept'}
            return {k: round(v, 3) for k, v in loadings.items()}
        except Exception:
            return {col: 0.0 for col in self.factors.columns}

    def compute_portfolio_factor_exposures(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Aggregates individual asset factor loadings into portfolio-level exposures."""
        factor_sums = {col: 0.0 for col in self.factors.columns}
        total_weight = sum(weights.values())
        
        if total_weight <= 0:
            return factor_sums

        for symbol, weight in weights.items():
            loadings = self.compute_asset_loadings(symbol)
            for factor, beta in loadings.items():
                if factor in factor_sums:
                    factor_sums[factor] += beta * (weight / total_weight)

        return {k: round(v, 3) for k, v in factor_sums.items()}
