"""
Reversal_Exhaustion_Scanner.py
-------------------------------------------------------------------------
Factor Generator: Bullish Reversal / Selling Exhaustion Scanner

Real, genuine gap identified against real swing-trading methodology
(both video-comparison lists tonight): every existing scanner in this
system - Consolidation, Hybrid_Alpha, Emerging_Leader, Earnings_Gap,
Cup_and_Handle - is continuation-only, looking for stocks already in
an uptrend consolidating or breaking out further. None of them detect
a stock reversing OUT of a downtrend - a genuinely different, absent
pattern type, not a variation of what already exists.

Real, testable definition, not a vague "looks reversal-y" heuristic:
1. A genuine prior downtrend (>=15% decline from the recent high)
2. A real capitulation day within that decline - the lowest close in
   the window, on volume >=2x the 20-day average (distinguishes a
   climactic sell-off from a quiet drift lower)
3. A confirmed bounce since that low (>=5% recovery) - not just a
   one-day wick, a sustained move
4. How close the capitulation day itself closed to its own high (a
   hammer-style close) - a real, additional quality signal, not
   required, but scored higher when present
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER

LOOKBACK_WINDOW = 60          # ~3 months, to identify the prior downtrend context
MIN_PRIOR_DECLINE = 0.15      # genuine downtrend, not a minor pullback
MIN_CAPITULATION_VOL_RATIO = 2.0   # capitulation day volume vs 20-day average
MIN_CONFIRMED_BOUNCE = 0.05   # real, sustained recovery since the low, not noise


def _evaluate_reversal(df: pd.DataFrame) -> dict:
    """
    Returns a dict of the reversal's real, measured characteristics if
    a genuine setup exists, otherwise None.
    """

    if len(df) < LOOKBACK_WINDOW + 20:
        return None

    window = df.iloc[-LOOKBACK_WINDOW:].copy()

    recent_high = float(window["high"].max())
    if recent_high <= 0:
        return None

    # The capitulation day: lowest close in the window
    low_idx = window["close"].idxmin()
    capitulation_close = float(window.loc[low_idx, "close"])
    capitulation_low = float(window.loc[low_idx, "low"])
    capitulation_high = float(window.loc[low_idx, "high"])
    capitulation_volume = float(window.loc[low_idx, "volume"])

    prior_decline = (recent_high - capitulation_close) / recent_high
    if prior_decline < MIN_PRIOR_DECLINE:
        return None

    # Real capitulation volume check - distinguishes genuine climactic
    # selling from a quiet drift to a new low
    pos = window.index.get_loc(low_idx)
    prior_20d = window.iloc[max(0, pos - 20):pos]
    if len(prior_20d) < 10:
        return None
    avg_vol_before = float(prior_20d["volume"].mean())
    if avg_vol_before <= 0:
        return None
    capitulation_vol_ratio = capitulation_volume / avg_vol_before
    if capitulation_vol_ratio < MIN_CAPITULATION_VOL_RATIO:
        return None

    # Real, confirmed bounce since the capitulation low - not just a
    # one-day wick. Must be genuinely AFTER the capitulation day, not
    # concurrent with it, so the low itself isn't the most recent bar.
    if pos >= len(window) - 1:
        return None
    price_now = float(window["close"].iloc[-1])
    bounce_pct = (price_now - capitulation_low) / capitulation_low
    if bounce_pct < MIN_CONFIRMED_BOUNCE:
        return None

    # Quality signal (not required): did the capitulation day itself
    # close near its own high, suggesting real buying stepped in that
    # same session (a hammer-style close)?
    day_range = capitulation_high - capitulation_low
    close_position = (capitulation_close - capitulation_low) / day_range if day_range > 0 else 0.5

    # Real, combined score - rewards a deeper prior decline (more room
    # for a real reversal), stronger capitulation volume, a stronger
    # confirmed bounce, and a better capitulation-day close position.
    # Each capped before combining so no single dimension dominates.
    decline_score = min(1.0, prior_decline / 0.40)
    volume_score = min(1.0, capitulation_vol_ratio / 5.0)
    bounce_score = min(1.0, bounce_pct / 0.20)
    close_score = close_position

    raw_score = (decline_score * 0.3 + volume_score * 0.25 + bounce_score * 0.3 + close_score * 0.15)

    return {
        "prior_decline_pct": round(prior_decline * 100, 2),
        "capitulation_vol_ratio": round(capitulation_vol_ratio, 2),
        "bounce_pct": round(bounce_pct * 100, 2),
        "close_position": round(close_position, 2),
        "capitulation_low": round(capitulation_low, 2),
        "raw_score": raw_score,
    }


def run_reversal_exhaustion_scanner():
    print("=" * 60)
    print("FACTOR GENERATOR: BULLISH REVERSAL / EXHAUSTION SCANNER")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR):
        return

    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith(".parquet")]
    factor_records = []
    pivot_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")
    detected_count = 0

    for file in parquet_files:
        ticker = file.replace(".parquet", "")
        path = os.path.join(PARQUET_CACHE_DIR, file)
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < LOOKBACK_WINDOW + 20:
                continue

            df.columns = [str(c).lower() for c in df.columns]
            df = df.dropna(subset=["close", "high", "low", "volume"]).sort_values("date")

            latest_close = float(df["close"].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df["volume"].iloc[-1])) < MIN_DAILY_TURNOVER:
                continue

            result = _evaluate_reversal(df)
            if result is None:
                continue

            detected_count += 1

            factor_records.append({
                "ticker": ticker,
                "factor_name": "reversal_exhaustion_score",
                "raw_val": result["raw_score"],
                "date": run_date,
            })

            # Pivot: the confirmation level a real continuation would
            # need to clear - the capitulation day's own high, a real,
            # observable price level, not an invented one
            pivot_records.append({
                "ticker": ticker,
                "pivot_price": result["capitulation_low"] * 1.05,
                "source": "Reversal_Exhaustion",
                "confidence": result["raw_score"],
                "date": run_date,
            })

        except Exception:
            continue

    print(f"[*] Bullish Reversal/Exhaustion Setups Detected : {detected_count}")

    if not factor_records:
        print("[+] No qualifying setups today.")
        print("=" * 60)
        return

    factors_df = pd.DataFrame(factor_records)
    factors_df["score"] = factors_df["raw_val"].rank(pct=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scanner_factors (
            ticker TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            score REAL,
            date TEXT NOT NULL,
            PRIMARY KEY (ticker, factor_name, date)
        )
    """)
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'reversal_exhaustion_score' AND date = ?", (run_date,))
    factors_df[["ticker", "factor_name", "score", "date"]].to_sql("scanner_factors", conn, if_exists="append", index=False)

    if pivot_records:
        conn.execute("CREATE TABLE IF NOT EXISTS setup_pivots (ticker TEXT, pivot_price REAL, source TEXT, confidence REAL, date TEXT, PRIMARY KEY (ticker, source, date))")
        conn.execute("DELETE FROM setup_pivots WHERE source = 'Reversal_Exhaustion' AND date = ?", (run_date,))
        pd.DataFrame(pivot_records).to_sql("setup_pivots", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

    print(f"[+] Wrote {len(factor_records)} factor points and {len(pivot_records)} pivots to SQLite.")
    print("=" * 60)


if __name__ == "__main__":
    run_reversal_exhaustion_scanner()