"""
core/indicators.py
-------------------------------------------------------------------------
Centralized technical indicator formulas to ensure mathematical 
consistency across all factor-generation scanners.
"""
import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Average True Range."""
    high = df["high"] if "high" in df.columns else df["High"]
    low = df["low"] if "low" in df.columns else df["Low"]
    close = df["close"] if "close" in df.columns else df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calculate_slope(series: pd.Series, window: int) -> float:
    """Calculates linear regression slope over a rolling window."""
    if len(series) < window:
        return 0.0
    y = np.log(series.tail(window).replace(0, np.nan)).dropna()
    if len(y) < (window // 2) or not np.isfinite(y).all():
        return 0.0
    return float(np.polyfit(np.arange(len(y)), y.values, 1)[0])

def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates Average Directional Index (ADX) over a given period."""
    try:
        high = df["high"] if "high" in df.columns else df["High"]
        low = df["low"] if "low" in df.columns else df["Low"]
        close = df["close"] if "close" in df.columns else df["Close"]
        
        up_move = high.diff()
        down_move = -low.diff()
        
        pdm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        mdm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        pdm_s, mdm_s = pd.Series(pdm, index=df.index), pd.Series(mdm, index=df.index)
        
        tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        pdi = 100 * (pdm_s.ewm(alpha=1/period, adjust=False).mean() / atr)
        mdi = 100 * (mdm_s.ewm(alpha=1/period, adjust=False).mean() / atr)
        
        dx = (abs(pdi - mdi) / abs(pdi + mdi)) * 100
        return float(dx.ewm(alpha=1/period, adjust=False).mean().iloc[-1])
    except Exception: 
        return 0.0
