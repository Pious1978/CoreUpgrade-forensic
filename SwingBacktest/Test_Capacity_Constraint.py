"""
SwingBacktest/Test_Capacity_Constraint.py

Direct test: is MAX_POSITIONS=10 genuinely suppressing how many of the
3-scanner candidate pool actually convert to trades? Runs the exact
same backtest twice - once at the real, default capacity (10
positions, 3 per sector), once with both capacity limits raised
substantially (30 positions, 9 per sector - same 3x ratio, removing
both potential ceilings at once for the clearest possible read).

Built because the overlap-only explanation (37.8% of candidates
shared across scanners) was real but insufficient - a genuine ~15%
increase in unique candidates still produced almost no trade-count
change, pointing at portfolio capacity as the more likely explanation.
This test settles it directly rather than continuing to infer.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Full_Backtest import run_full_backtest


def run_capacity_test():

    print()
    print("=" * 70)
    print("CAPACITY CONSTRAINT TEST")
    print("=" * 70)

    print("\n--- BASELINE: MAX_POSITIONS=10, MAX_PER_SECTOR=3 (real, default) ---")
    run_full_backtest(max_positions=10, max_per_sector=3, table_name="backtest_trades_cap10")

    print("\n--- EXPANDED: MAX_POSITIONS=30, MAX_PER_SECTOR=9 (capacity ceilings removed) ---")
    run_full_backtest(max_positions=30, max_per_sector=9, table_name="backtest_trades_cap30")

    print("\n" + "=" * 70)
    print("Compare the two RESULTS SUMMARY blocks above directly.")
    print("If total_trades increases substantially at higher capacity,")
    print("MAX_POSITIONS was genuinely the binding constraint.")
    print("If total_trades barely changes even with 3x the capacity,")
    print("something else (entry conditions, watch window) is the real limit.")
    print("=" * 70)


if __name__ == "__main__":
    run_capacity_test()