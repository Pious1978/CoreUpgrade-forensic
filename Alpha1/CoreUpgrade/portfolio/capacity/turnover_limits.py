import numpy as np
import pandas as pd

class TurnoverLimits:
    """Calculates and enforces portfolio turnover and rebalance limits."""
    
    def __init__(self, max_annual_turnover: float = 4.0):
        self.max_turnover = max_annual_turnover

    def calculate_turnover(self, old_weights: np.ndarray, new_weights: np.ndarray) -> float:
        return float(np.sum(np.abs(new_weights - old_weights)))

    def enforce_turnover(self, old_weights: np.ndarray, new_weights: np.ndarray) -> bool:
        to = self.calculate_turnover(old_weights, new_weights)
        return to <= self.max_turnover
