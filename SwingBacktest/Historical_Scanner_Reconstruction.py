"""
SwingBacktest/Historical_Scanner_Reconstruction.py

#54B - Historical scanner reconstruction. Real, scoped, expanding pass.

HONEST SCOPING: the live system's canonical signal source is an
ensemble of 5 discovery scanners (Consolidation_Scanner.py,
Hybrid_Alpha_Scanner.py, Emerging_Leader_Scanner.py,
Earnings_Gap_Scanner.py, Cup_and_Handle.py). Of these, only 3 produce
a real, usable pivot (entry trigger) - Consolidation_Scanner.py,
Hybrid_Alpha_Scanner.py, and Cup_and_Handle.py. The other 2
(Emerging_Leader_Scanner.py, Earnings_Gap_Scanner.py) are cross-
sectional ranking factors with no pivot of their own, meant to adjust
pivot-scanner candidates downstream via Pivot_Consensus_Engine.py -
reconstructing them meaningfully is a genuinely different, separate
task, not covered here.

This reconstructs 2 of the 3 pivot-producing scanners now
(Consolidation_Scanner.py, Cup_and_Handle.py). Hybrid_Alpha_Scanner.py
remains a real, deferred next step.

Reuses each scanner's exact, real evaluation functions and exact real
thresholds - "same logic, different data provider," not a second
implementation. Both scanners' core functions take only a DataFrame
and return a dict; zero file I/O, zero date dependency, confirmed
genuinely reusable as-is with no modification needed to either live
file.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Historical_Data_Provider import PointInTimeMarketData
from Consolidation_Scanner import _evaluate_consolidation, MIN_CONFIDENCE
from Cup_and_Handle import _evaluate_cup, _evaluate_handle, _evaluate_volume_in_handle
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


def reconstruct_cup_and_handle_at_date(data, as_of_date):
    """
    Reconstructs what Cup_and_Handle.py would have flagged as real
    candidates at this exact historical date. Matches the live
    scanner's exact chain and classification: a cup with no handle yet
    produces no usable pivot (correctly skipped); a handle within 12%
    of pivot is COMPLETE (full confidence), further away is
    HANDLE_FORMING (confidence reduced by the same 0.8 factor the live
    scanner applies).
    """

    view = data.as_of(as_of_date)
    candidates = []

    for ticker in view.get_available_tickers():

        df = view.get_price_history(ticker)

        if df is None or len(df) < 80:  # matches the live scanner's own minimum
            continue

        try:
            latest_close = float(df["close"].iloc[-1])
            latest_volume = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0

            if latest_close < MIN_PRICE or (latest_close * latest_volume) < MIN_DAILY_TURNOVER:
                continue

            cup = _evaluate_cup(df)

            if cup is None:
                continue

            handle = _evaluate_handle(df, cup)

            if handle is None:
                continue  # CUP_ONLY - no real pivot yet, matching the live scanner exactly

            pivot = handle["pivot"]
            pivot_dist = (pivot - latest_close) / pivot

            raw_confidence = (cup["cup_score"] + handle["handle_score"] +
                               _evaluate_volume_in_handle(handle)) / 30.0

            if pivot_dist > 0.12:
                pattern_name = "HANDLE_FORMING"
                confidence = raw_confidence * 0.8
            else:
                pattern_name = "COMPLETE"
                confidence = raw_confidence

            candidates.append({
                "ticker": ticker,
                "pivot": pivot,
                "pattern": pattern_name,
                "confidence": confidence,
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
    print("HISTORICAL SCANNER RECONSTRUCTION - 2 of 5 (Consolidation + Cup & Handle)")
    print("=" * 70)
    print("Honest scope: this reconstructs 2 of the 3 pivot-producing")
    print("discovery scanners. Hybrid_Alpha_Scanner.py is a real, deferred")
    print("next step; the 2 factor/ranking scanners are a separate task.")
    print()

    init_historical_candidates_table()

    data = PointInTimeMarketData()

    dates_to_process = data.trading_dates[::sample_every_n_days]

    print(f"[*] Reconstructing candidates for {len(dates_to_process)} historical dates "
          f"(sampling every {sample_every_n_days} trading day(s))...")

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    total_candidates = 0
    total_by_scanner = {"Consolidation_Scanner": 0, "Cup_and_Handle": 0}

    for i, as_of_date in enumerate(dates_to_process):

        if i > 0 and i % 10 == 0:
            print(f"[*] Progress: {i}/{len(dates_to_process)} dates processed, "
                  f"{total_candidates} candidates found so far "
                  f"(Consolidation: {total_by_scanner['Consolidation_Scanner']}, "
                  f"Cup&Handle: {total_by_scanner['Cup_and_Handle']})...")
            conn.commit()  # periodic checkpoint

        date_str = as_of_date.strftime("%Y-%m-%d")

        consolidation_candidates = reconstruct_candidates_at_date(data, as_of_date)
        cup_handle_candidates = reconstruct_cup_and_handle_at_date(data, as_of_date)

        for c in consolidation_candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"], "Consolidation_Scanner"))

        for c in cup_handle_candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"], "Cup_and_Handle"))

        total_by_scanner["Consolidation_Scanner"] += len(consolidation_candidates)
        total_by_scanner["Cup_and_Handle"] += len(cup_handle_candidates)
        total_candidates += len(consolidation_candidates) + len(cup_handle_candidates)

    conn.commit()
    conn.close()

    print(f"\n[+] {total_candidates} total historical candidates found across "
          f"{len(dates_to_process)} dates, written to {BACKTEST_DB_PATH}")
    print(f"    Consolidation_Scanner: {total_by_scanner['Consolidation_Scanner']}")
    print(f"    Cup_and_Handle: {total_by_scanner['Cup_and_Handle']}")
    print("=" * 70)


if __name__ == "__main__":
    run()