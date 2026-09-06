"""
SwingBacktest/Compare_Time_Stop_Scenarios.py

#71 backtest follow-up: runs the full backtest with and without the
time stop enabled, into separate, permanent tables (same established
pattern as Compare_Sensitivity_Trades.py's volume-confirmation
comparison), then reports the actual metrics side by side. Answers a
direct question: was trapped capital in stagnant positions a real,
material drag on the already-validated result, or a smaller effect
than expected?

Does not touch or overwrite backtest_trades (the original, validated
baseline) - both scenarios here get their own explicit table names.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Full_Backtest import run_full_backtest


def run_both_and_compare():

    print()
    print("=" * 70)
    print("TIME STOP SCENARIO COMPARISON")
    print("=" * 70)

    print("\n--- Running WITHOUT time stop (matches the original, validated baseline) ---")
    metrics_without = run_full_backtest(
        table_name="backtest_trades_no_timestop", enable_time_stop=False
    )

    print("\n--- Running WITH time stop enabled ---")
    metrics_with = run_full_backtest(
        table_name="backtest_trades_with_timestop", enable_time_stop=True
    )

    print()
    print("=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(f"{'Metric':<25} {'Without time stop':<20} {'With time stop':<20}")
    print("-" * 70)

    for key in ["return_pct", "profit_factor", "win_rate_pct", "total_trades"]:
        val_without = metrics_without.get(key, "N/A") if metrics_without else "N/A"
        val_with = metrics_with.get(key, "N/A") if metrics_with else "N/A"
        print(f"{key:<25} {str(val_without):<20} {str(val_with):<20}")

    print("=" * 70)


if __name__ == "__main__":
    run_both_and_compare()