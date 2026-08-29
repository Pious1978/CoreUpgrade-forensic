"""
technical_indicators.py

Computes structural/technical context from bhav-copy-derived parquet
data: 20-day EMA discount, 5-vs-20 day volume contraction (V-Dry), and 
real stock-specific Average True Range (ATR).

These are historical/end-of-day calculations, not live intraday - they
use whatever the parquet cache currently has, refreshed each night by
bhav_to_parquet_converter.py.

Needs at least 25 trading days of history for a given ticker to compute
technical context (20 for the EMA to be minimally meaningful, plus 5 more for the
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


def compute_atr(ticker, period=14):
    """
    Computes a real, stock-specific Average True Range from bhav-copy
    history, instead of the flat 3%-of-price estimate used previously
    (which applied the same assumed volatility to every stock regardless
    of how it actually behaves - real testing showed this both over- and
    under-estimated volatility depending on the stock, e.g. a stable
    large-cap like RELIANCE genuinely runs closer to 1.7%, not 3%).

    Returns (atr_absolute, atr_pct_of_price) or (None, None) if there
    isn't enough history yet for a genuine 14-day reading.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None, None

    try:
        df = pd.read_parquet(path).sort_values("date")

        if len(df) < period + 1:
            return None, None

        prev_close = df["close"].shift(1)

        true_range = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = float(true_range.rolling(window=period).mean().iloc[-1])
        current_close = float(df["close"].iloc[-1])

        if current_close <= 0:
            return None, None

        atr_pct = round((atr / current_close) * 100, 2)

        return round(atr, 2), atr_pct

    except Exception:
        return None, None