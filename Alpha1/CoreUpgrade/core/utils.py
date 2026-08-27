"""
core/utils.py
-------------------------------------------------------------------------
Shared utility functions for safe mathematical operations and formatting.
"""
import numpy as np
import pandas as pd

def safe_div(a, b):
    """Safely divides two numbers or pandas Series, handling division by zero."""
    try:
        if isinstance(a, pd.Series) or isinstance(b, pd.Series):
            return a.divide(b).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        if b is None or b == 0 or (isinstance(b, float) and np.isnan(b)):
            return 0.0
        if a is None or (isinstance(a, float) and np.isnan(a)):
            return 0.0
        return float(a / b)
    except Exception:
        return 0.0
