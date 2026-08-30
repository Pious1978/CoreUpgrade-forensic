"""
Fibonacci_Retracement_Scanner.py

General-purpose 61.8% Fibonacci retracement entry scanner - adapted
from Alpha1's real alpha_strategist.py. Genuinely different from how
Bear_Market_Scanner.py already uses Fibonacci zones: that scanner only
applies this within a specific, deep (25-80%) 52-week pullback context
for stocks showing bear-market value characteristics. This is the
general case - any stock, in any regime, that has pulled back to its
own 61.8% retracement level within a recent 6-month range, the "Golden
Ratio" pullback entry technique used across multiple of your own tools
(also appears independently in this repo's Analystfallback.py).

Fully price-based, no fundamentals dependency - uses our own real,
backfilled parquet_cache rather than a live yfinance download, so this
is usable right now, no Monday dependency.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, UNIVERSE_CSV_PATH, BASE_DIR
from core.excel_utils import save_excel_with_retry

LOOKBACK_DAYS = 126  # roughly 6 months of trading days
ZONE_TOLERANCE_PCT = 5.0
MIN_PRICE = 20
MIN_VOLUME = 200000


def load_universe():
    """Reuses the same NSE_EQ.csv universe file every other scanner in
    this pipeline already relies on, for consistency."""

    try:
        df = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            print("[-] SYMBOL column missing from universe file.")
            return []

        symbol_col = df.columns[cols.index("SYMBOL")]
        symbols = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()

        return sorted(set(s for s in symbols if len(s) >= 2))

    except Exception as e:
        print(f"[-] Error loading universe: {e}")
        return []


def check_fibonacci_zone(current_price, high_6m, low_6m, tolerance_pct=ZONE_TOLERANCE_PCT):
    """
    Real logic from alpha_strategist.py - is price at or below the
    tolerance-adjusted 61.8% retracement level? A deeper pullback still
    counts (the condition is <=, not a narrow band), since the original
    intent is "at this level or a genuinely better price," not an exact
    match.
    """

    fib_zone = high_6m - (0.618 * (high_6m - low_6m))
    is_in_zone = current_price <= (fib_zone * (1 + tolerance_pct / 100))
    distance_pct = ((current_price - fib_zone) / fib_zone) * 100 if fib_zone > 0 else None

    return is_in_zone, round(fib_zone, 2), round(distance_pct, 2) if distance_pct is not None else None


def analyze_stock(ticker):
    """
    Real technical analysis from our own backfilled parquet_cache - no
    live data needed, unlike the original script's live yfinance
    download.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # Only drop rows missing the price data this needs - a blanket
        # dropna() would also drop backfilled rows missing
        # delivery_qty/delivery_pct (intentionally NULL for Yahoo-
        # sourced history). Same real bug found and fixed across
        # several other scanners tonight.
        df = df.dropna(subset=["close", "high", "low"])

        if len(df) < LOOKBACK_DAYS:
            return None

        recent = df.tail(LOOKBACK_DAYS)

        current_price = float(recent["close"].iloc[-1])

        if current_price < MIN_PRICE:
            return None

        avg_volume = float(df["volume"].tail(20).mean())
        if avg_volume < MIN_VOLUME:
            return None

        high_6m = float(recent["high"].max())
        low_6m = float(recent["low"].min())

        if high_6m <= low_6m:
            return None

        is_in_zone, fib_level, distance_pct = check_fibonacci_zone(current_price, high_6m, low_6m)

        if not is_in_zone:
            return None

        # Real, simple, transparent risk framing - matching the
        # original script's directness rather than pulling in the full
        # dynamic R:R machinery built for the live execution board,
        # since this is meant to be a quick, standalone screening tool.
        recent_low = float(recent["low"].tail(30).min())
        risk_per_share = round(current_price - recent_low, 2)

        if risk_per_share <= 0:
            return None

        target = round(high_6m, 2)
        reward_per_share = round(target - current_price, 2)
        rr = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else None

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "high_6m": round(high_6m, 2),
            "low_6m": round(low_6m, 2),
            "fib_618_level": fib_level,
            "distance_from_fib_pct": distance_pct,
            "stop_loss": recent_low,
            "target": target,
            "rr": rr,
        }

    except Exception:
        return None


def run():

    print()
    print("=" * 70)
    print("FIBONACCI RETRACEMENT SCANNER - 61.8% PULLBACK ENTRIES")
    print("=" * 70)

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    print(f"[*] Scanning {len(symbols)} stocks for genuine pullbacks to their "
          f"61.8% retracement level (within {ZONE_TOLERANCE_PCT}% tolerance)...")

    results = []

    for symbol in symbols:
        result = analyze_stock(symbol)
        if result:
            results.append(result)

    if not results:
        print("\n[+] No stocks currently sitting at their 61.8% retracement level.")
        return

    result_df = pd.DataFrame(results).sort_values("distance_from_fib_pct")

    today = datetime.now().strftime("%Y-%m-%d")
    result_df["date"] = today

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fibonacci_retracement_candidates (
            ticker TEXT,
            current_price REAL,
            high_6m REAL,
            low_6m REAL,
            fib_618_level REAL,
            distance_from_fib_pct REAL,
            stop_loss REAL,
            target REAL,
            rr REAL,
            date TEXT,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("DELETE FROM fibonacci_retracement_candidates WHERE date = ?", (today,))
    result_df.to_sql("fibonacci_retracement_candidates", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, "FIBONACCI_RETRACEMENT_WATCHLIST.xlsx")
    save_excel_with_retry(result_df, excel_path, index=False)

    print(f"\n[+] {len(result_df)} stocks found at their 61.8% retracement level:")
    print(result_df.to_string(index=False))
    print(f"\n[+] Written to fibonacci_retracement_candidates and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()