import pandas as pd
from typing import Dict, Any

class ADVEngine:
    """Calculates Average Daily Volume (ADV) and Median Daily Value metrics."""
    
    def __init__(self, volume_df: pd.DataFrame, close_df: pd.DataFrame):
        self.volume = volume_df.sort_index()
        self.close = close_df.sort_index()
        self.turnover_df = self.volume * self.close

    def compute_adv_metrics(self, symbol: str) -> Dict[str, float]:
        if symbol not in self.volume.columns or symbol not in self.close.columns:
            return {"adv_20_days": 0.0, "adv_60_days": 0.0, "median_daily_value": 0.0}

        v_series = self.volume[symbol].dropna()
        t_series = self.turnover_df[symbol].dropna()

        adv_20 = float(v_series.tail(20).mean()) if len(v_series) >= 20 else float(v_series.mean())
        adv_60 = float(v_series.tail(60).mean()) if len(v_series) >= 60 else float(v_series.mean())
        median_val = float(t_series.tail(60).median()) if len(t_series) >= 60 else float(t_series.median())

        return {
            "adv_20_shares": round(adv_20, 2),
            "adv_60_shares": round(adv_60, 2),
            "median_daily_value": round(median_val, 2)
        }
