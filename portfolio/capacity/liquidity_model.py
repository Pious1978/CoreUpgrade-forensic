import pandas as pd
from typing import Dict, Any

class LiquidityModel:
    """Computes a normalized liquidity rating (0-100) based on ADV, spread, and free float."""
    
    def __init__(self, adv_engine: ADVEngine):
        self.adv_engine = adv_engine

    def compute_liquidity_score(self, symbol: str, spread_pct: float, free_float_pct: float) -> Dict[str, Any]:
        metrics = self.adv_engine.compute_adv_metrics(symbol)
        median_val = metrics["median_daily_value"]

        # Liquidity scoring heuristics
        value_score = min(50.0, (median_val / 50_000_000) * 50.0) # Baseline ₹5 Cr daily value = 50 pts
        spread_score = max(0.0, 30.0 - (spread_pct * 1000.0)) # Lower spread = higher score
        float_score = (free_float_pct / 100.0) * 20.0

        total_score = round(min(100.0, max(0.0, value_score + spread_score + float_score)), 2)

        return {
            "symbol": symbol,
            "liquidity_score": total_score,
            "rating": "HIGH" if total_score >= 75 else ("MODERATE" if total_score >= 40 else "ILLIQUID")
        }
