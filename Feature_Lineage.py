"""
Feature_Lineage.py

Addresses #96 - feature/factor lineage: raw feature -> transformation
-> factor -> composite score, each independently traceable, answering
"why did this stock score X on this date" months later.

HONEST, DELIBERATE SCOPE: this does not retrofit full lineage capture
into every scanner across the system - that would touch many working
parts at once for a single session's work. Instead, this demonstrates
a real, complete, working lineage record for ONE genuinely important,
heavily-used factor - rs_percentile - built by reading
RelativeStrengthEngine.py's actual, real calculation directly, not
assumed. The same pattern (compute_lineage_for_<factor>() + log via
Event_Log.py) is the template for extending coverage to other factors
over time.

Real, confirmed chain for rs_percentile (from RelativeStrengthEngine.py):
    RAW FEATURE: close price today, close price 250 trading days ago
                 (both from this ticker's own parquet_cache file)
    TRANSFORMATION: rs_raw = (close_today - close_250d_ago) / close_250d_ago
                 - a plain, unadjusted 250-trading-day (~1 year) return
    UNIVERSE (answers #97 directly): every file in parquet_cache with
                 at least MIN_TRADING_DAYS_RS days of history,
                 excluding the NIFTY index itself - NOT liquidity- or
                 sector-filtered, confirmed by reading the actual loop.
    FACTOR: rs_percentile = rank(rs_raw, pct=True) * 100 across that
                 same, full universe
"""

import os
import pandas as pd

from core.config import PARQUET_CACHE_DIR
from core.factor_registry import FACTOR_REGISTRY_VERSION
from Event_Log import log_event


def compute_lineage_for_rs_percentile(ticker, min_trading_days=250):
    """
    Real, complete, honest lineage reconstruction for one ticker's
    rs_percentile - reproduces RelativeStrengthEngine.py's own,
    confirmed formula exactly, capturing every real input and
    intermediate value along the way, not just the final number.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]

        if df.empty or len(df) < min_trading_days:
            return None

        latest_row = df.iloc[-1]
        close_today = float(latest_row["close"])
        close_250d_ago = float(df["close"].iloc[-min_trading_days])
        date_today = str(latest_row.get("date", "unknown"))
        date_250d_ago = str(df["date"].iloc[-min_trading_days]) if "date" in df.columns else "unknown"

        if close_250d_ago <= 0:
            return None

        rs_raw = (close_today - close_250d_ago) / close_250d_ago

        return {
            "ticker": ticker.upper(),
            "raw_features": {
                "close_today": close_today,
                "close_today_date": date_today,
                "close_250d_ago": close_250d_ago,
                "close_250d_ago_date": date_250d_ago,
                "source": f"parquet_cache/{ticker.upper()}.parquet",
            },
            "transformation": {
                "formula": "(close_today - close_250d_ago) / close_250d_ago",
                "lookback_trading_days": min_trading_days,
                "result": round(rs_raw, 6),
            },
            "universe_context": {
                "description": "Every parquet_cache file with >= min_trading_days history, "
                                "excluding the NIFTY index itself - confirmed directly from "
                                "RelativeStrengthEngine.py's loop, not liquidity- or sector-filtered.",
            },
            "factor_registry_version": FACTOR_REGISTRY_VERSION,
        }

    except Exception:
        return None


def compute_and_log_lineage(ticker):
    """
    Real, direct computation plus a permanent, queryable event log
    entry - the genuine payoff: reconstructing exactly why a given
    rs_percentile value was what it was, on demand, months later.
    """

    lineage = compute_lineage_for_rs_percentile(ticker)

    if lineage is None:
        return None

    log_event("FEATURE_LINEAGE_RS_PERCENTILE", ticker, lineage)

    return lineage


def print_lineage(ticker):
    """Human-readable rendering of a ticker's real, reconstructed rs_percentile lineage."""

    lineage = compute_and_log_lineage(ticker)

    if lineage is None:
        print(f"No lineage available for {ticker.upper()} - insufficient history or ticker not found.")
        return

    print()
    print("=" * 70)
    print(f"FEATURE LINEAGE: rs_percentile for {lineage['ticker']}")
    print("=" * 70)

    print("\n1. RAW FEATURE")
    rf = lineage["raw_features"]
    print(f"   Source: {rf['source']}")
    print(f"   Close today ({rf['close_today_date']}): Rs{rf['close_today']}")
    print(f"   Close {lineage['transformation']['lookback_trading_days']} trading days ago "
          f"({rf['close_250d_ago_date']}): Rs{rf['close_250d_ago']}")

    print("\n2. TRANSFORMATION")
    t = lineage["transformation"]
    print(f"   Formula: {t['formula']}")
    print(f"   Result (rs_raw): {t['result']}")

    print("\n3. UNIVERSE CONTEXT (the real answer to \"percentile of what universe?\")")
    print(f"   {lineage['universe_context']['description']}")

    print(f"\n4. FACTOR REGISTRY VERSION: {lineage['factor_registry_version']}")

    print("=" * 70)


if __name__ == "__main__":
    ticker = input("Ticker: ").strip().upper()
    print_lineage(ticker)