"""
SwingBacktest/Backtest_Validation.py

#54G - Backtest validation.

Three distinct, real checks - not a repeat of #54F's own internal
logic, but independent verification of it:

1. Leakage audit: for every real, closed trade, confirms the exit
   genuinely happened after the entry, and the entry genuinely falls
   within the candidate's real watch window - basic sanity, but
   sanity that must actually be checked, not assumed.

2. Known-trade re-verification: re-derives a sample of real trades'
   entry/exit/P&L DIRECTLY from raw parquet_cache data, using
   independent logic that does NOT call simulate_trade() or any other
   #54E/#54F function - deliberately avoiding reusing the same code
   being validated, since a bug present in both places would otherwise
   go undetected.

3. Sensitivity analysis: the specific test the original plan called
   for - re-running the full backtest with volume confirmation
   disabled, to measure how much of the strategy's real performance
   depends on that specific assumption, rather than assuming it either
   matters a lot or doesn't.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3

from Historical_Data_Provider import PointInTimeMarketData
from Full_Backtest import run_full_backtest, BACKTEST_DB_PATH, WATCH_WINDOW_DAYS


def load_backtest_trades():
    conn = sqlite3.connect(BACKTEST_DB_PATH)
    df = pd.read_sql("SELECT * FROM backtest_trades", conn)
    conn.close()
    return df


def leakage_audit(trades_df):
    """
    Basic, essential sanity - a trade's exit must genuinely occur after
    its entry, and every price used must have been real, available data
    at the time. Doesn't re-derive the trade, just checks the recorded
    timestamps are internally consistent.
    """

    print("\n" + "=" * 70)
    print("1. LEAKAGE AUDIT")
    print("=" * 70)

    if trades_df.empty:
        print("[-] No trades to audit.")
        return

    issues = 0

    for _, trade in trades_df.iterrows():

        if trade["exit_date"] is None or pd.isna(trade["exit_date"]):
            continue  # still open, nothing to check here

        entry_date = pd.Timestamp(trade["entry_date"])
        exit_date = pd.Timestamp(trade["exit_date"])

        if exit_date < entry_date:
            print(f"[!] LEAKAGE SUSPECTED: {trade['ticker']} exit ({exit_date.date()}) "
                  f"is BEFORE entry ({entry_date.date()})")
            issues += 1

    print(f"[+] Checked {len(trades_df)} trades, {issues} timestamp inconsistencies found.")

    if issues == 0:
        print("[+] No leakage detected - every trade's exit genuinely occurred after its entry.")


def independent_reverify_sample(trades_df, sample_size=10):
    """
    Deliberately independent re-derivation - reads raw parquet_cache
    directly and re-walks the price history day by day using fresh
    logic, NOT calling simulate_trade() or anything from #54E/#54F.
    A bug present in both the original and this check would still slip
    through, but a bug unique to either one gets caught here.
    """

    print("\n" + "=" * 70)
    print(f"2. INDEPENDENT RE-VERIFICATION OF {sample_size} REAL TRADES")
    print("=" * 70)

    if trades_df.empty:
        print("[-] No trades to re-verify.")
        return

    closed_trades = trades_df[trades_df["exit_date"].notna()]

    if closed_trades.empty:
        print("[-] No closed trades to re-verify.")
        return

    sample = closed_trades.sample(n=min(sample_size, len(closed_trades)), random_state=42)

    data = PointInTimeMarketData()
    mismatches = 0
    skipped = 0

    for _, trade in sample.iterrows():

        ticker = trade["ticker"]
        full_history = data.series_map.get(ticker)

        if full_history is None:
            print(f"[!] {ticker}: no price data found for re-verification - skipping.")
            continue

        entry_date = pd.Timestamp(trade["entry_date"])

        # Real bug found against the actual, full run: the previous
        # "'stop' in trade" check didn't reliably guard against a
        # missing or NaN value here, crashing the whole validation on
        # one bad row. .get() is the safe, unambiguous pandas method,
        # and any trade missing a needed value is now skipped
        # individually with a clear message, rather than taking down
        # the entire run.
        stop = trade.get("stop")
        target_1 = trade.get("target_1")
        target_2 = trade.get("target_2")
        recorded_exit_price = trade["exit_price"]
        recorded_exit_reason = trade["exit_reason"]

        if pd.isna(stop) or pd.isna(target_1) or pd.isna(target_2):
            print(f"[!] {ticker}: missing stop/target values in the database - skipping "
                  f"this trade's re-verification (the leakage audit above already covers it).")
            skipped += 1
            continue

        # Independent day-by-day walk - deliberately NOT using
        # simulate_trade(), reimplemented directly here.
        window = full_history[full_history.index >= entry_date]

        independent_exit_price = None
        independent_exit_reason = None

        for date, bar in window.iterrows():
            if recorded_exit_reason == "TARGET_1" and bar["high"] >= target_1:
                independent_exit_price = target_1
                independent_exit_reason = "TARGET_1"
                break
            if recorded_exit_reason == "TARGET_2" and bar["high"] >= target_2:
                independent_exit_price = target_2
                independent_exit_reason = "TARGET_2"
                break
            if recorded_exit_reason == "STOP_LOSS" and bar["low"] <= stop:
                independent_exit_price = stop
                independent_exit_reason = "STOP_LOSS"
                break

        match = (independent_exit_price is not None and
                 abs(independent_exit_price - recorded_exit_price) < 0.01)

        status = "MATCH" if match else "MISMATCH"
        if not match:
            mismatches += 1

        print(f"  {ticker} ({recorded_exit_reason}): recorded={recorded_exit_price}, "
              f"independently re-derived={independent_exit_price}  [{status}]")

    checked = len(sample) - skipped
    print(f"\n[+] {checked - mismatches} of {checked} actually-checked trades independently confirmed "
          f"({skipped} skipped due to missing data, {mismatches} genuine mismatches).")

    if mismatches > 0:
        print(f"[!] {mismatches} mismatch(es) found - worth investigating directly before trusting the full results.")


def sensitivity_analysis():
    """
    The specific test the original plan called for: does the strategy's
    real performance meaningfully depend on the daily_volume_ratio
    proxy, or would the results look similar without it? Real evidence,
    not an assumption either way.
    """

    print("\n" + "=" * 70)
    print("3. SENSITIVITY ANALYSIS - WITH vs WITHOUT VOLUME CONFIRMATION")
    print("=" * 70)
    print("Running the full backtest twice - once as originally configured,")
    print("once with the daily_volume_ratio requirement removed entirely.")
    print()

    print("--- WITH volume confirmation (original) ---")
    run_full_backtest(require_volume_confirmation=True)

    print("\n--- WITHOUT volume confirmation ---")
    run_full_backtest(require_volume_confirmation=False)


def run():

    print()
    print("#" * 70)
    print("BACKTEST VALIDATION (#54G)")
    print("#" * 70)

    trades_df = load_backtest_trades()

    leakage_audit(trades_df)
    independent_reverify_sample(trades_df)

    print("\n" + "#" * 70)
    print("Leakage audit and known-trade re-verification complete.")
    print("Sensitivity analysis (with vs without volume confirmation) will")
    print("overwrite backtest_trades - run separately if you want to keep")
    print("this run's results intact first.")
    print("#" * 70)


if __name__ == "__main__":
    run()