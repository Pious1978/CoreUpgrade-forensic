"""
technical_indicators.py

Computes structural/technical context from bhav-copy-derived parquet
data: 20-day EMA discount and 5-vs-20 day volume contraction (V-Dry).

These are historical/end-of-day calculations, not live intraday - they
use whatever the parquet cache currently has, refreshed each night by
bhav_to_parquet_converter.py.

Needs at least 25 trading days of history for a given ticker to compute
anything (20 for the EMA to be minimally meaningful, plus 5 more for the
trailing volume window). Returns None values below that, rather than a
misleadingly early/unstable number.
"""

import os
import pandas as pd

from core.config import PARQUET_CACHE_DIR


def get_technical_context(ticker):

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return {"ema20": None, "discount_pct": None, "vdry_ratio": None}

    try:
        df = pd.read_parquet(path).sort_values("date")

        if len(df) < 25:
            return {"ema20": None, "discount_pct": None, "vdry_ratio": None}

        ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        current_close = float(df["close"].iloc[-1])
        discount_pct = round(((current_close - ema20) / ema20) * 100, 2)

        recent_vol = float(df["volume"].tail(5).mean())
        baseline_vol = float(df["volume"].iloc[-25:-5].mean())
        vdry_ratio = round(recent_vol / baseline_vol, 2) if baseline_vol > 0 else None

        return {
            "ema20": round(ema20, 2),
            "discount_pct": discount_pct,
            "vdry_ratio": vdry_ratio,
        }

    except Exception:
        return {"ema20": None, "discount_pct": None, "vdry_ratio": None}