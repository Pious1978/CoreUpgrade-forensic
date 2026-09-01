"""
Morning_Briefing.py

#55 - Unified daily workflow / Morning Briefing.

Pure orchestration - every section reads from real, existing tables or
calls real, existing functions already built and tested tonight.
Nothing here duplicates logic that already lives elsewhere:

- Regime: reads market_regime (Market_Regime_Engine.py's real output)
- Kill switch: calls check_kill_switch() (#58, as-is)
- Open positions: reads trade_journal (Trade_Journal.py's real schema)
- New candidates: reads trade_candidates (Risk_Positioning_Engine.py's
  real output)
- Recent alerts: reads today's entries from alerts.log (#56, as-is)
- Tax: points to Tax_Report.py (#57) rather than reimplementing any
  classification logic here

The goal, per the plan: tell the operator what requires attention,
rather than requiring them to remember which scripts to run.
"""

import sqlite3
import pandas as pd
from datetime import datetime

from core.config import DB_PATH
from core.kill_switch import check_kill_switch

TOTAL_CAPITAL_DEFAULT = 1000000  # matches Risk_Positioning_Engine.py's own default


def section_regime():

    print("\n" + "-" * 70)
    print("MARKET REGIME")
    print("-" * 70)

    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT date, regime, confidence, breadth_50 FROM market_regime
            ORDER BY date DESC LIMIT 1
        """).fetchone()
        conn.close()

        if row is None:
            print("[!] No regime data found - run Market_Regime_Engine.py.")
            return

        date, regime, confidence, breadth_50 = row
        print(f"  {regime} (confidence: {confidence}), as of {date}")
        if breadth_50 is not None:
            print(f"  50-day breadth: {breadth_50:.1f}%")

    except Exception as e:
        print(f"[!] Could not read regime: {e}")


def section_kill_switch():

    print("\n" + "-" * 70)
    print("KILL SWITCH STATUS")
    print("-" * 70)

    result = check_kill_switch(TOTAL_CAPITAL_DEFAULT)

    if result["blocked"]:
        print(f"  🛑 ACTIVE [{result['severity']}] - {result['reason']}")
    else:
        print(f"  ✅ Normal - {result['reason']}")
        if "daily_loss_pct" in result:
            print(f"  Today: {result['daily_loss_pct']:.2f}% realized loss, "
                  f"this week: {result['weekly_loss_pct']:.2f}%")


def section_open_positions():

    print("\n" + "-" * 70)
    print("OPEN POSITIONS")
    print("-" * 70)

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT ticker, entry_price, entry_date, planned_stop, planned_target_1
            FROM trade_journal WHERE status != 'CLOSED'
        """, conn)
        conn.close()

        if df.empty:
            print("  No open positions.")
        else:
            print(df.to_string(index=False))

    except Exception as e:
        print(f"[!] Could not read open positions: {e}")


def section_new_candidates(top_n=10):

    print("\n" + "-" * 70)
    print(f"NEW HIGH-CONVICTION CANDIDATES (top {top_n})")
    print("-" * 70)

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"""
            SELECT ticker, Composite_Score, Tier FROM trade_candidates
            ORDER BY Composite_Score DESC LIMIT {top_n}
        """, conn)
        conn.close()

        if df.empty:
            print("  No candidates found - run the discovery pipeline first.")
        else:
            print(df.to_string(index=False))

    except Exception as e:
        print(f"[!] Could not read candidates: {e}")


def section_recent_alerts():

    print("\n" + "-" * 70)
    print("TODAY'S ALERTS")
    print("-" * 70)

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        with open("alerts.log") as f:
            lines = [line for line in f if line.startswith(f"[{today}")]

        if not lines:
            print("  No alerts yet today.")
        else:
            for line in lines:
                print(f"  {line.strip()}")

    except FileNotFoundError:
        print("  No alerts logged yet.")


def section_tax_reminder():

    print("\n" + "-" * 70)
    print("TAX")
    print("-" * 70)
    print("  Run 'python Tax_Report.py' for the current STCG/LTCG estimate.")


def run():

    print()
    print("=" * 70)
    print(f"MORNING BRIEFING - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    section_regime()
    section_kill_switch()
    section_open_positions()
    section_new_candidates()
    section_recent_alerts()
    section_tax_reminder()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run()