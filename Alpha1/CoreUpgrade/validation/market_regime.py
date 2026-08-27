"""
validation/market_regime.py
Institutional Market Regime Classification Engine

Classifies historical time-series data and individual trade records into 
distinct macro environments (BULL, BEAR, HIGH_VOL, CRISIS) based on index trend 
(200 DMA), volatility spikes (India VIX), and breadth structure.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union
from datetime import datetime


class MarketRegimeClassifier:
    def __init__(
        self, 
        market_data: pd.DataFrame, 
        vix_high_threshold: float = 25.0,
        vix_crisis_threshold: float = 35.0,
        crisis_drawdown_pct: float = 20.0
    ):
        """
        Initializes the institutional market regime classifier.

        Args:
            market_data: DataFrame containing ['date', 'nifty_close', 'vix', 'advance_decline_ratio'].
            vix_high_threshold: Volatility level defining high volatility regimes (default 25.0).
            vix_crisis_threshold: Volatility level defining systemic crisis spikes (default 35.0).
            crisis_drawdown_pct: Peak-to-trough drawdown threshold for market crashes (default 20.0%).
        """
        self.df = market_data.copy()
        self.vix_high = vix_high_threshold
        self.vix_crisis = vix_crisis_threshold
        self.crisis_dd = crisis_drawdown_pct
        
        self._preprocess_data()

    def _preprocess_data(self):
        """Prepares time series, computes 200 DMA, and calculates rolling peak drawdowns."""
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'])
            self.df = self.df.sort_values('date').reset_index(drop=True)
        else:
            raise ValueError("market_data DataFrame must contain a 'date' column.")
        
        if 'nifty_close' in self.df.columns:
            # Compute 200-day moving average for macro trend filtering
            self.df['nifty_200_dma'] = self.df['nifty_close'].rolling(window=200, min_periods=30).mean()
            # Compute rolling peak for crash/crisis drawdown evaluation
            self.df['rolling_peak'] = self.df['nifty_close'].cummax()
            self.df['drawdown_from_peak_pct'] = ((self.df['nifty_close'] - self.df['rolling_peak']) / self.df['rolling_peak']) * 100.0
        else:
            raise ValueError("market_data DataFrame must contain 'nifty_close' for regime identification.")

    def classify_dates(self) -> pd.DataFrame:
        """
        Classifies each date row into a specific institutional regime.
        
        Returns:
            DataFrame updated with the 'market_regime' categorical tag.
        """
        regimes = []
        
        for _, row in self.df.iterrows():
            close = row.get('nifty_close', 0.0)
            dma200 = row.get('nifty_200_dma', close)
            vix = row.get('vix', 15.0)
            dd = row.get('drawdown_from_peak_pct', 0.0)
            ad_ratio = row.get('advance_decline_ratio', 1.0) # Breadth health indicator
            
            # Institutional Classification Hierarchy
            if dd <= -self.crisis_dd and vix >= self.vix_crisis:
                regime = "CRISIS"
            elif vix >= self.vix_high:
                regime = "HIGH_VOL"
            elif close < dma200 or ad_ratio < 0.7:
                regime = "BEAR"
            else:
                regime = "BULL"
            
            regimes.append(regime)
            
        self.df['market_regime'] = regimes
        return self.df

    def tag_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enriches raw trade records with their corresponding macro market regime based on trade date.

        Args:
            trades: List of trade dictionaries containing a 'date' key.

        Returns:
            List of trade dictionaries updated with the 'market_regime' tag.
        """
        if 'market_regime' not in self.df.columns:
            self.classify_dates()

        # Create a fast lookup map from date to regime
        regime_map = dict(zip(self.df['date'].dt.strftime('%Y-%m-%d'), self.df['market_regime']))
        sorted_dates = sorted(regime_map.keys())

        tagged_trades = []
        for trade in trades:
            trade_copy = trade.copy()
            date_val = trade_copy.get("date")
            
            if date_val:
                date_str = str(date_val)[:10]
                if date_str in regime_map:
                    trade_copy["market_regime"] = regime_map[date_str]
                else:
                    # Find the closest previous date if exact match is absent
                    past_dates = [d for d in sorted_dates if d <= date_str]
                    if past_dates:
                        trade_copy["market_regime"] = regime_map[past_dates[-1]]
                    else:
                        trade_copy["market_regime"] = "BULL"
            else:
                trade_copy["market_regime"] = "BULL"
                
            tagged_trades.append(trade_copy)

        return tagged_trades
