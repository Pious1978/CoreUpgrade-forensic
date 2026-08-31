"""
SwingBacktest/Historical_Scanner_Reconstruction.py

#54B - Historical scanner reconstruction. Real, scoped first pass.

HONEST SCOPING: the live system's canonical signal source is an
ensemble of 5 discovery scanners (Consolidation_Scanner.py,
Hybrid_Alpha_Scanner.py, Emerging_Leader_Scanner.py,
Earnings_Gap_Scanner.py, Cup_and_Handle.py). Reconstructing all 5
across hundreds of historical dates would be a genuinely enormous
compute undertaking. This first pass reconstructs ONE - Consolidation_
Scanner.py, chosen as the first-listed, most directly reusable
scanner - to get an honest, real, if partial, signal before committing
to the full 5-scanner reconstruction. The other 4 remain a real,
explicitly deferred next step, not silently dropped.

Reuses Consolidation_Scanner.py's exact, real _evaluate_consolidation()
function and its exact real thresholds (MIN_PRICE, MIN_DAILY_TURNOVER,
MIN_CONFIDENCE) - "same logic, different data provider," not a second
implementation. That function takes only a DataFrame and returns a
dict; zero file I/O, zero date dependency, confirmed genuinely reusable
as-is with no modification needed to the live file at all.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Historical_Data_Provider import PointInTimeMarketData
from Consolidation_Scanner import _evaluate_consolidation, MIN_CONFIDENCE
from core.config import MIN_PRICE, MIN_DAILY_TURNOVER

BACKTEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.db")


def init_historical_candidates_table():

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_candidates (
            date TEXT,
            ticker TEXT,
            pivot REAL,
            pattern TEXT,
            confidence REAL,
            source_scanner TEXT,
            PRIMARY KEY (date, ticker, source_scanner)
        )
    """)
    conn.commit()
    conn.close()


def reconstruct_candidates_at_date(data, as_of_date):
    """
    Reconstructs what Consolidation_Scanner.py would have flagged as
    real candidates at this exact historical date, using only price
    history available through that date - the same real filters and
    thresholds the live scanner actually uses.
    """

    view = data.as_of(as_of_date)
    candidates = []

    for ticker in view.get_available_tickers():

        df = view.get_price_history(ticker)

        if df is None or len(df) < 65:  # BASE_MAX_DAYS, matching the live scanner's own requirement
            continue

        try:
            latest_close = float(df["close"].iloc[-1])
            latest_volume = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0

            if latest_close < MIN_PRICE or (latest_close * latest_volume) < MIN_DAILY_TURNOVER:
                continue

            base = _evaluate_consolidation(df)

            if base is None or base["confidence"] < MIN_CONFIDENCE:
                continue

            pattern_name = "Tight_Flag" if base["depth"] <= 0.10 and base["length"] <= 21 else "Consolidation"

            candidates.append({
                "ticker": ticker,
                "pivot": base["pivot"],
                "pattern": pattern_name,
                "confidence": base["confidence"],
            })

        except Exception:
            continue

    return candidates


def run(sample_every_n_days=5):
    """
    Real, smaller first pass by default - matches the same sampling
    approach already used in #54C, for the same reason: an honest,
    faster initial signal before committing to full daily granularity.
    """

    print()
    print("=" * 70)
    print("HISTORICAL SCANNER RECONSTRUCTION - CONSOLIDATION SCANNER (1 of 5)")
    print("=" * 70)
    print("Honest scope: this reconstructs ONE of the 5 real discovery")
    print("scanners. The other 4 are a real, deferred next step.")
    print()

    init_historical_candidates_table()

    data = PointInTimeMarketData()

    dates_to_process = data.trading_dates[::sample_every_n_days]

    print(f"[*] Reconstructing candidates for {len(dates_to_process)} historical dates "
          f"(sampling every {sample_every_n_days} trading day(s))...")

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    total_candidates = 0

    for i, as_of_date in enumerate(dates_to_process):

        if i > 0 and i % 10 == 0:
            print(f"[*] Progress: {i}/{len(dates_to_process)} dates processed, "
                  f"{total_candidates} candidates found so far...")
            conn.commit()  # periodic checkpoint

        candidates = reconstruct_candidates_at_date(data, as_of_date)

        date_str = as_of_date.strftime("%Y-%m-%d")

        for c in candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"], "Consolidation_Scanner"))

        total_candidates += len(candidates)

    conn.commit()
    conn.close()

    print(f"\n[+] {total_candidates} total historical candidates found across "
          f"{len(dates_to_process)} dates, written to {BACKTEST_DB_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    run()