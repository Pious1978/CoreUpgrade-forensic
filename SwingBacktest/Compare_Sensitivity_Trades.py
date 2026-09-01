"""
SwingBacktest/Compare_Sensitivity_Trades.py

Direct, trade-level comparison between the "with volume confirmation"
and "without volume confirmation" backtest runs - built to answer a
specific question: does removing volume confirmation change WHICH
stocks get traded, or just WHEN the same stocks get entered?

Runs both scenarios into separate, permanent tables (rather than the
sensitivity_analysis() function's overwrite-in-place approach), then
classifies every ticker into one of three groups:

- SAME_TIMING: appears in both runs, entered on the same date
- DIFFERENT_TIMING: appears in both runs, entered on a different date
  (the volume confirmation requirement delayed or advanced entry)
- ONLY_WITH_VOLUME / ONLY_WITHOUT_VOLUME: appears in only one run
  entirely (a genuinely different candidate set, not a timing shift)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Full_Backtest import run_full_backtest, BACKTEST_DB_PATH


def run_both_and_compare():

    print()
    print("=" * 70)
    print("TRADE-LEVEL SENSITIVITY COMPARISON")
    print("=" * 70)

    print("\n--- Running WITH volume confirmation ---")
    run_full_backtest(require_volume_confirmation=True, table_name="backtest_trades_with_vol")

    print("\n--- Running WITHOUT volume confirmation ---")
    run_full_backtest(require_volume_confirmation=False, table_name="backtest_trades_without_vol")

    conn = sqlite3.connect(BACKTEST_DB_PATH)
    with_vol = pd.read_sql("SELECT ticker, entry_date, exit_date, pnl FROM backtest_trades_with_vol", conn)
    without_vol = pd.read_sql("SELECT ticker, entry_date, exit_date, pnl FROM backtest_trades_without_vol", conn)
    conn.close()

    # A ticker can appear multiple times (re-entered after a prior exit),
    # so match on (ticker, entry_date) pairs specifically, not just ticker
    with_vol["key"] = with_vol["ticker"] + "_" + with_vol["entry_date"]
    without_vol["key"] = without_vol["ticker"] + "_" + without_vol["entry_date"]

    with_tickers = set(with_vol["ticker"])
    without_tickers = set(without_vol["ticker"])

    same_timing = 0
    different_timing = []

    # For tickers present in both, check whether entry dates actually match
    common_tickers = with_tickers & without_tickers

    for ticker in common_tickers:
        with_dates = set(with_vol[with_vol["ticker"] == ticker]["entry_date"])
        without_dates = set(without_vol[without_vol["ticker"] == ticker]["entry_date"])

        if with_dates == without_dates:
            same_timing += 1
        else:
            different_timing.append({
                "ticker": ticker,
                "with_vol_dates": sorted(with_dates),
                "without_vol_dates": sorted(without_dates),
            })

    only_with_vol = with_tickers - without_tickers
    only_without_vol = without_tickers - with_tickers

    print("\n" + "-" * 70)
    print("RESULTS")
    print("-" * 70)
    print(f"Tickers traded in BOTH scenarios, SAME entry date: {same_timing}")
    print(f"Tickers traded in BOTH scenarios, DIFFERENT entry date: {len(different_timing)}")
    print(f"Tickers traded ONLY with volume confirmation: {len(only_with_vol)}")
    print(f"Tickers traded ONLY without volume confirmation: {len(only_without_vol)}")

    total_common = same_timing + len(different_timing)
    if total_common > 0:
        timing_share = len(different_timing) / total_common * 100
        print(f"\nOf tickers common to both runs, {timing_share:.1f}% show a genuine "
              f"timing difference rather than an identical entry.")

    if different_timing:
        print("\n[+] Sample of tickers with different entry timing:")
        for item in different_timing[:10]:
            print(f"  {item['ticker']}: with_vol={item['with_vol_dates']}, "
                  f"without_vol={item['without_vol_dates']}")

    print("\n[+] Sample tickers ONLY in the without-volume-confirmation run:")
    for t in list(only_without_vol)[:10]:
        print(f"  {t}")

    print("=" * 70)


if __name__ == "__main__":
    run_both_and_compare()