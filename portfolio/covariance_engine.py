import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

class CovarianceEngine:
    """
    Institutional covariance engine utilizing sklearn's analytic Ledoit-Wolf 
    shrinkage estimator to guarantee positive-definiteness across high-dimensional universes.
    """
    
    def __init__(self, price_history: pd.DataFrame):
        self.prices = price_history.sort_index()
        self.returns = self.prices.pct_change().dropna()

    def compute_ledoit_wolf_covariance(self) -> pd.DataFrame:
        lw = LedoitWolf()
        lw.fit(self.returns.values)
        shrunk_cov = lw.covariance_
        
        # Annualized covariance matrix (252 trading days)
        ann_cov = shrunk_cov * 252
        return pd.DataFrame(ann_cov, index=self.returns.columns, columns=self.returns.columns)

    def get_portfolio_variance(self, weights: np.ndarray, cov_matrix: pd.DataFrame) -> float:
        w = np.array(weights)
        return float(np.dot(w.T, np.dot(cov_matrix.values, w)))
