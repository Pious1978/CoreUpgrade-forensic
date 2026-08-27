"""
Feature_Store_Factory.py
-------------------------------------------------------------------------
Enterprise Feature Engineering Factory - Single Pass Mathematical Matrix
"""
import pandas as pd
import numpy as np
from Standard_Engine_Types import FeatureStore

class FeatureStoreFactory:
    @staticmethod
    def generate(symbol: str, date_str: str, price_df: pd.DataFrame, nifty_df: pd.DataFrame, rs_snapshot: float) -> FeatureStore:
        """Transforms raw multi-horizon price series arrays into a static FeatureStore wrapper."""
        if price_df.empty:
            raise ValueError(f"Cannot generate features for empty dataframe on symbol: {symbol}")

        # Defensively extract series data independent of MultiIndex layout variations
        close = price_df["Close"].dropna()
        high = price_df["High"].dropna()
        low = price_df["Low"].dropna()
        vol = price_df["Volume"].dropna()

        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        if isinstance(vol, pd.DataFrame): vol = vol.iloc[:, 0]

        current_price = float(close.iloc[-1])

        # Core Mathematical Indicators (Calculated exactly once)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        raw_atr = tr.rolling(14).mean().iloc[-1]
        atr_pct = (raw_atr / current_price) * 100.0

        sma50 = close.rolling(50).mean().iloc[-1]
        sma50_dist = (current_price - sma50) / sma50
        
        high_20 = high.rolling(20).max().iloc[-1]
        low_20 = low.rolling(20).min().iloc[-1]
        range_compression_20 = ((high_20 - low_20) / low_20) * 100

        avg_vol_20 = vol.tail(20).mean()
        rvol = vol.iloc[-1] / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Pack structured calculated vectors into our metrics matrix dictionary
        calculated_metrics = {
            "atr_pct": round(float(atr_pct), 4),
            "range_compression_20": round(float(range_compression_20), 4),
            "rvol": round(float(rvol), 4),
            "sma50_dist": round(float(sma50_dist), 4),
            "rs_percentile": float(rs_snapshot)
        }

        return FeatureStore(
            symbol=symbol.replace(".NS", ""),
            date=date_str,
            close_price=current_price,
            metrics=calculated_metrics,
            raw_dfs={"price_df": price_df, "nifty_df": nifty_df}
        )