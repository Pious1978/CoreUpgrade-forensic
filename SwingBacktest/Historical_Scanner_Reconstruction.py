"""
SwingBacktest/Historical_Scanner_Reconstruction.py

#54B - Historical scanner reconstruction. Real, scoped, expanding pass.

HONEST SCOPING: the live system's canonical signal source is an
ensemble of 5 discovery scanners. Of these, only 3 produce a real,
usable pivot (entry trigger) - Consolidation_Scanner.py,
Hybrid_Alpha_Scanner.py, and Cup_and_Handle.py - all 3 are now
reconstructed here. Emerging_Leader_Scanner.py is a cross-sectional
ranking factor with no pivot of its own - but its accumulation_ratio
has a real, defined 8% weight in core/factor_registry.py's live
Composite_Score formula (confirmed directly - unlike
Earnings_Gap_Scanner.py's earnings_gap_strength, which has NO entry in
FACTOR_DEFINITIONS at all and is genuinely dead code in the live
system). accumulation_ratio is therefore blended into each pivot
candidate's confidence at that same real weight, rather than treated
as an independent candidate source it structurally can't be.
Earnings_Gap_Scanner.py is correctly excluded - adapting a signal the
live system doesn't actually use would test nothing meaningful.

Reuses each scanner's exact, real evaluation functions and exact real
thresholds - "same logic, different data provider," not a second
implementation. All core functions take only a DataFrame and return a
dict/value; zero file I/O, zero date dependency, confirmed genuinely
reusable as-is with no modification needed to any live file's
behavior (Emerging_Leader_Scanner.py's extraction into
_evaluate_accumulation() was tested to produce identical results).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Historical_Data_Provider import PointInTimeMarketData
from Consolidation_Scanner import _evaluate_consolidation, MIN_CONFIDENCE
from Cup_and_Handle import _evaluate_cup, _evaluate_handle, _evaluate_volume_in_handle
from Hybrid_Alpha_Scanner import _evaluate_vcp, VCP_MAX_DAYS
from Emerging_Leader_Scanner import _evaluate_accumulation
from core.config import MIN_PRICE, MIN_DAILY_TURNOVER

BACKTEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.db")

ACCUMULATION_RATIO_WEIGHT = 0.08  # matches core/factor_registry.py's real, live weight exactly


def blend_accumulation_ratio(pattern_confidence, df):
    """
    Blends the real accumulation_ratio into a pivot candidate's
    confidence at its actual, defined live weight (8%) - honest
    approximation, not a full Composite_Score replica (which would
    need rs_percentile, delivery_score, and other factors this
    backtest doesn't compute). Treats the existing pattern confidence
    as "everything else" and accumulation_ratio as its real,
    documented additional contribution.

    Requires >= 50 rows (Emerging_Leader_Scanner.py's own real minimum)
    - returns the original confidence unchanged if there isn't enough
    history, rather than fabricating a value.
    """

    if df is None or len(df) < 50:
        return pattern_confidence, None

    accum_ratio = _evaluate_accumulation(df)

    blended = pattern_confidence * (1 - ACCUMULATION_RATIO_WEIGHT) + accum_ratio * ACCUMULATION_RATIO_WEIGHT

    return blended, accum_ratio


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

    # Real lesson from earlier tonight: CREATE TABLE IF NOT EXISTS does
    # NOT add a new column to a table that already exists from a prior
    # run. ALTER TABLE with a try/except is the safe way to add this
    # column regardless of whether the table is new or already present.
    try:
        conn.execute("ALTER TABLE historical_candidates ADD COLUMN accumulation_ratio REAL")
    except sqlite3.OperationalError:
        pass  # column already exists from a previous run

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

            blended_confidence, accum_ratio = blend_accumulation_ratio(base["confidence"], df)

            candidates.append({
                "ticker": ticker,
                "pivot": base["pivot"],
                "pattern": pattern_name,
                "confidence": blended_confidence,
                "accumulation_ratio": accum_ratio,
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

            blended_confidence, accum_ratio = blend_accumulation_ratio(confidence, df)

            candidates.append({
                "ticker": ticker,
                "pivot": pivot,
                "pattern": pattern_name,
                "confidence": blended_confidence,
                "accumulation_ratio": accum_ratio,
            })

        except Exception:
            continue

    return candidates


def reconstruct_hybrid_alpha_at_date(data, as_of_date):
    """
    Reconstructs what Hybrid_Alpha_Scanner.py would have flagged as
    real candidates at this exact historical date. Simpler, single-
    stage evaluation than Cup_and_Handle.py - _evaluate_vcp() either
    qualifies (confidence >= MIN_CONFIDENCE) or returns None entirely,
    no intermediate "forming" classification.
    """

    view = data.as_of(as_of_date)
    candidates = []

    for ticker in view.get_available_tickers():

        df = view.get_price_history(ticker)

        if df is None or len(df) < VCP_MAX_DAYS:  # matches the live scanner's own minimum
            continue

        try:
            latest_close = float(df["close"].iloc[-1])
            latest_volume = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0

            if latest_close < MIN_PRICE or (latest_close * latest_volume) < MIN_DAILY_TURNOVER:
                continue

            vcp = _evaluate_vcp(df)

            if vcp is None:
                continue

            blended_confidence, accum_ratio = blend_accumulation_ratio(vcp["confidence"], df)

            candidates.append({
                "ticker": ticker,
                "pivot": vcp["pivot"],
                "pattern": "VCP",
                "confidence": blended_confidence,
                "accumulation_ratio": accum_ratio,
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
    print("HISTORICAL SCANNER RECONSTRUCTION - 3 of 5 (Consolidation + Cup & Handle + Hybrid Alpha)")
    print("=" * 70)
    print("Honest scope: this reconstructs all 3 pivot-producing discovery")
    print("scanners. The 2 factor/ranking scanners are a separate task.")
    print()

    init_historical_candidates_table()

    data = PointInTimeMarketData()

    dates_to_process = data.trading_dates[::sample_every_n_days]

    print(f"[*] Reconstructing candidates for {len(dates_to_process)} historical dates "
          f"(sampling every {sample_every_n_days} trading day(s))...")

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    total_candidates = 0
    total_by_scanner = {"Consolidation_Scanner": 0, "Cup_and_Handle": 0, "Hybrid_Alpha": 0}

    for i, as_of_date in enumerate(dates_to_process):

        if i > 0 and i % 10 == 0:
            print(f"[*] Progress: {i}/{len(dates_to_process)} dates processed, "
                  f"{total_candidates} candidates found so far "
                  f"(Consolidation: {total_by_scanner['Consolidation_Scanner']}, "
                  f"Cup&Handle: {total_by_scanner['Cup_and_Handle']}, "
                  f"Hybrid Alpha: {total_by_scanner['Hybrid_Alpha']})...")
            conn.commit()  # periodic checkpoint

        date_str = as_of_date.strftime("%Y-%m-%d")

        consolidation_candidates = reconstruct_candidates_at_date(data, as_of_date)
        cup_handle_candidates = reconstruct_cup_and_handle_at_date(data, as_of_date)
        hybrid_alpha_candidates = reconstruct_hybrid_alpha_at_date(data, as_of_date)

        for c in consolidation_candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner, accumulation_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"],
                  "Consolidation_Scanner", c.get("accumulation_ratio")))

        for c in cup_handle_candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner, accumulation_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"],
                  "Cup_and_Handle", c.get("accumulation_ratio")))

        for c in hybrid_alpha_candidates:
            conn.execute("""
                INSERT OR REPLACE INTO historical_candidates
                (date, ticker, pivot, pattern, confidence, source_scanner, accumulation_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date_str, c["ticker"], c["pivot"], c["pattern"], c["confidence"],
                  "Hybrid_Alpha", c.get("accumulation_ratio")))

        total_by_scanner["Consolidation_Scanner"] += len(consolidation_candidates)
        total_by_scanner["Cup_and_Handle"] += len(cup_handle_candidates)
        total_by_scanner["Hybrid_Alpha"] += len(hybrid_alpha_candidates)
        total_candidates += len(consolidation_candidates) + len(cup_handle_candidates) + len(hybrid_alpha_candidates)

    conn.commit()
    conn.close()

    print(f"\n[+] {total_candidates} total historical candidates found across "
          f"{len(dates_to_process)} dates, written to {BACKTEST_DB_PATH}")
    print(f"    Consolidation_Scanner: {total_by_scanner['Consolidation_Scanner']}")
    print(f"    Cup_and_Handle: {total_by_scanner['Cup_and_Handle']}")
    print(f"    Hybrid_Alpha: {total_by_scanner['Hybrid_Alpha']}")
    print("=" * 70)


if __name__ == "__main__":
    run()