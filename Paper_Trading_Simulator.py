"""
Paper_Trading_Simulator.py

Connects the five real, previously-unconnected paper-trading files
found tonight (Execution_Order_Manager.py, Position_Manager.py,
Exit_Engine.py, Performance_Analytics.py, Portfolio_Risk_Controller.py)
into one coherent workflow. Each file was fully functional on its own,
but nothing ever called them in sequence.

Purpose: objectively, automatically measure the scanner ecosystem's
hypothetical performance over time - "if I had taken every single
signal this system generated, what would my real win rate and
performance actually be?" - entirely separate from Trade_Journal.py's
real trade tracking. Uses its own `positions` table, never touches
trade_journal, and never represents real money or real decisions.

Real sequence each run:
1. Execution_Order_Manager.py - creates a new paper position for every
   sized candidate in trade_candidates that isn't already an open paper
   position, now correctly stopping at Portfolio_Risk_Controller.py's
   MAX_POSITIONS ceiling (previously computed but never actually
   enforced).
2. Position_Manager.py - trails the stop upward on any open position
   that's moved 10%+ into profit.
3. Exit_Engine.py - closes any open position that's hit its stop or
   either target, using live prices.
4. Performance_Analytics.py - reports real, cumulative win rate and P&L
   across every closed paper position to date.

Safe to run repeatedly (e.g., once per session alongside
Live_Execution_Monitor.py) - duplicate protection means it won't
re-open a position that's already tracked, and closed positions stay
closed.
"""

import Execution_Order_Manager as eom
import Position_Manager as pm
import Exit_Engine as ee
import Performance_Analytics as pa
from Portfolio_Risk_Controller import check_portfolio_limits


def run():

    print()
    print("=" * 70)
    print("PAPER TRADING SIMULATOR - OBJECTIVE SIGNAL PERFORMANCE TRACKING")
    print("=" * 70)
    print("Simulated positions only - this never represents real money or")
    print("real decisions. Tracks 'what if I took every signal' separately")
    print("from your real trades in Trade_Journal.py.")
    print()

    print("[1/4] Checking for new candidates to open as paper positions...")
    eom.init_positions_table()
    created = eom.execute_entries()
    print(f"      {created} new paper position(s) opened.")

    print("\n[2/4] Trailing stops on open positions...")
    pm.update_positions()
    print("      Done.")

    print("\n[3/4] Checking open positions against live prices for exits...")
    ee.process_exits()
    print("      Done.")

    print("\n[4/4] Real, cumulative performance across all paper trades to date:")
    pa.generate_report()

    limits = check_portfolio_limits()
    print(f"\n[*] Currently {limits['positions']} open paper position(s), "
          f"Rs{limits['capital_used']:,.0f} simulated capital deployed.")

    print("=" * 70)


if __name__ == "__main__":
    run()