"""
SwingBacktest/Historical_Regime_Reconstruction.py

#54C - Historical regime reconstruction.

Reuses Market_Regime_Engine.py's real, live breadth and regime
classification logic exactly as-is - "same logic, different data
provider," not a second implementation. The only change made to that
file was adding an optional point_in_time_view parameter to
compute_breadth_and_returns(), confirmed backward-compatible (the live,
nightly pipeline's call site never passes it).

Reconstructs what regime the system would have classified at every
real historical trading date, using only data available through that
date (via #54A's PointInTimeMarketData) - directly needed by #54E's
position sizing, since risk_budget scales with the regime's
position_multiplier at the time of each historical trade, not today's
regime.

Writes to this backtest's own, dedicated database - never touches
rs_delivery_history.db, keeping this entirely separate from the live
system per the agreed containment design.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Historical_Data_Provider import PointInTimeMarketData
from Market_Regime_Engine import compute_breadth_and_returns, MarketRegimeEngine
from core.config import PARQUET_CACHE_DIR, NIFTY_BENCHMARK_SYMBOL

BACKTEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.db")


def init_historical_regime_table():

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_regime (
            date TEXT PRIMARY KEY,
            regime TEXT,
            confidence TEXT,
            composite_score REAL,
            breadth_20 REAL,
            breadth_50 REAL,
            breadth_200 REAL,
            position_multiplier REAL
        )
    """)
    conn.commit()
    conn.close()


def reconstruct_regime_at_date(data, as_of_date, engine):
    """
    Reconstructs the regime classification for one historical date,
    using only data available through that date. Returns None if there
    isn't yet enough real history (mirrors the live system's own
    genuine minimum-history requirements, not an artificial gap).
    """

    view = data.as_of(as_of_date)

    nifty_history = view.get_price_history(NIFTY_BENCHMARK_SYMBOL)

    if nifty_history is None or len(nifty_history) < 200:
        return None

    nifty_df = nifty_history.copy()
    nifty_df["sma_50"] = nifty_df["close"].rolling(50).mean()
    nifty_df["sma_200"] = nifty_df["close"].rolling(200).mean()

    if pd.isna(nifty_df["sma_200"].iloc[-1]):
        return None

    breadth_data, all_stocks_returns = compute_breadth_and_returns(
        PARQUET_CACHE_DIR, NIFTY_BENCHMARK_SYMBOL, point_in_time_view=view
    )

    if breadth_data.get("breadth_20", 0) == 0 and breadth_data.get("breadth_50", 0) == 0:
        return None  # genuinely insufficient real data this early in history

    result = engine.evaluate_market_breadth_and_regime(nifty_df, breadth_data, all_stocks_returns)

    return result


def run(sample_every_n_days=5):
    """
    Real, smaller first pass by default - reconstructs regime every N
    trading days rather than every single day, matching the agreed
    "smaller pass first" approach before committing to full daily
    granularity. Set sample_every_n_days=1 for full reconstruction
    later.
    """

    print()
    print("=" * 70)
    print("HISTORICAL REGIME RECONSTRUCTION")
    print("=" * 70)

    init_historical_regime_table()

    data = PointInTimeMarketData()
    engine = MarketRegimeEngine()

    dates_to_process = data.trading_dates[::sample_every_n_days]

    print(f"[*] Reconstructing regime for {len(dates_to_process)} historical dates "
          f"(sampling every {sample_every_n_days} trading day(s))...")

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    results = []

    for i, as_of_date in enumerate(dates_to_process):

        if i > 0 and i % 20 == 0:
            print(f"[*] Progress: {i}/{len(dates_to_process)} dates processed...")

        result = reconstruct_regime_at_date(data, as_of_date, engine)

        if result is None:
            continue

        date_str = as_of_date.strftime("%Y-%m-%d")

        conn.execute("""
            INSERT OR REPLACE INTO historical_regime
            (date, regime, confidence, composite_score, breadth_20, breadth_50, breadth_200, position_multiplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date_str, result["regime"], result["confidence"], result["composite_score"],
            result["breadth_20"], result["breadth_50"], result["breadth_200"], result["position_multiplier"]
        ))

        results.append(result["regime"])

    conn.commit()
    conn.close()

    print(f"\n[+] {len(results)} historical regime classifications written to {BACKTEST_DB_PATH}")

    if results:
        regime_counts = pd.Series(results).value_counts()
        print("\n[+] Regime distribution across reconstructed history:")
        print(regime_counts.to_string())

    print("=" * 70)


if __name__ == "__main__":
    run()