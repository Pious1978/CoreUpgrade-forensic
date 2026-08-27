"""
validation/market_data_features.py
Institutional Market Data Feature Engineering Engine

Converts raw market time-series data into normalized quantitative features 
(trend strength, volatility percentiles, breadth moving averages, and chop indicators) 
for institutional market regime classification and strategy stress-testing.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class MarketDataFeatureEngineer:
    def __init__(self, market_data: pd.DataFrame):
        """
        Initializes the market data feature engineering engine.

        Args:
            market_data: DataFrame containing ['date', 'nifty_close', 'vix', 'advance_decline_ratio'].
        """
        self.df = market_data.copy()
        self._validate_and_sort()

    def _validate_and_sort(self):
        """Validates input schema and ensures chronological ordering without look-ahead contamination."""
        required_cols = ['date', 'nifty_close', 'vix', 'advance_decline_ratio']
        for col in required_cols:
            if col not in self.df.columns:
                raise ValueError(f"Market data DataFrame is missing required column: '{col}'")

        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.sort_values('date').reset_index(drop=True)

    def generate_features(self) -> pd.DataFrame:
        """
        Executes the feature engineering pipeline to compute institutional market features.

        Returns:
            DataFrame enriched with institutional feature columns.
        """
        # 1. Trend Features (Strict 200 DMA without look-ahead bias - min_periods=200)
        self.df['nifty_200_dma'] = self.df['nifty_close'].rolling(window=200, min_periods=200).mean()
        self.df['distance_from_200_dma_pct'] = np.where(
            self.df['nifty_200_dma'].notna(),
            ((self.df['nifty_close'] - self.df['nifty_200_dma']) / self.df['nifty_200_dma']) * 100.0,
            np.nan
        )

        # 2. Volatility Features (252-day rolling VIX percentile for regime boundaries)
        self.df['vix_percentile'] = self.df['vix'].rolling(window=252, min_periods=60).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        ) * 100.0
        self.df['vix_ma20'] = self.df['vix'].rolling(window=20, min_periods=5).mean()

        # 3. Breadth Features (20-day moving average of advance/decline ratio)
        self.df['breadth_ma20'] = self.df['advance_decline_ratio'].rolling(window=20, min_periods=5).mean()

        # 4. Drawdown from Peak (For systemic crisis and bear detection)
        self.df['rolling_peak'] = self.df['nifty_close'].cummax()
        self.df['drawdown_from_peak_pct'] = (
            (self.df['nifty_close'] - self.df['rolling_peak']) / self.df['rolling_peak']
        ) * 100.0

        # 5. Chop / Sideways Market Proxy (Trend Efficiency Ratio over 10 sessions)
        net_change = (self.df['nifty_close'] - self.df['nifty_close'].shift(10)).abs()
        sum_abs_changes = self.df['nifty_close'].diff().abs().rolling(window=10).sum()
        self.df['trend_efficiency_ratio'] = np.where(
            sum_abs_changes > 0, net_change / sum_abs_changes, 0.0
        )

        return self.df
