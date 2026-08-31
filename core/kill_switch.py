"""
core/kill_switch.py

#58 - Real kill switch, adapted from a genuine, simple concept found in
governance/kill_switch.py during tonight's OMS-spine investigation
(daily/weekly loss thresholds, tiered severity). That original version
assumed an automated LIQUIDATE_AND_HALT action requiring live broker
integration we don't have - this adapts the real, useful part (loss
threshold detection) to what actually fits: blocking NEW position
sizing when triggered, plus an explicit manual override, checked
before Risk_Positioning_Engine.py sizes any candidate.

Real P&L source: aggregates realized_pnl from trade_journal (full
exits) AND trade_journal_exits (partial exits, from #26) - a partial
exit's loss is real and should count toward the kill switch just as
much as a full one.
"""

import sqlite3
from datetime import datetime, timedelta

from core.config import DB_PATH

MAX_DAILY_LOSS_PCT = 3.0    # configurable - blocks new positions if today's realized loss exceeds this
MAX_WEEKLY_LOSS_PCT = 6.0   # configurable - blocks new positions if this week's realized loss exceeds this

MANUAL_OVERRIDE_FILE = "KILL_SWITCH_ACTIVE.txt"  # presence of this file = manual emergency stop


def get_realized_pnl_since(since_date):
    """
    Real, aggregated realized P&L since a given date, combining full
    exits (trade_journal) and partial exits (trade_journal_exits) -
    both are real, already-realized losses/gains.
    """

    try:
        conn = sqlite3.connect(DB_PATH)

        full_exits = conn.execute("""
            SELECT COALESCE(SUM(realized_pnl), 0) FROM trade_journal
            WHERE status = 'CLOSED' AND exit_date >= ?
        """, (since_date,)).fetchone()[0]

        partial_exits = conn.execute("""
            SELECT COALESCE(SUM(realized_pnl), 0) FROM trade_journal_exits
            WHERE exit_date >= ?
        """, (since_date,)).fetchone()[0]

        conn.close()

        return float(full_exits) + float(partial_exits)

    except Exception:
        return 0.0


def check_manual_override():
    """Explicit, manual emergency stop - presence of this file blocks
    all new position sizing regardless of any P&L threshold. A simple,
    direct way to halt everything by hand, no code changes needed."""

    import os
    return os.path.exists(MANUAL_OVERRIDE_FILE)


def check_kill_switch(total_capital,
                       max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
                       max_weekly_loss_pct=MAX_WEEKLY_LOSS_PCT):
    """
    Real, authoritative kill switch check - call this BEFORE sizing any
    new position. Returns a clear status dict; callers should block new
    sizing entirely if blocked=True, regardless of severity.
    """

    if check_manual_override():
        return {
            "blocked": True,
            "severity": "MANUAL",
            "reason": f"Manual override active - {MANUAL_OVERRIDE_FILE} exists. "
                      f"Delete this file to resume.",
        }

    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    daily_pnl = get_realized_pnl_since(today)
    weekly_pnl = get_realized_pnl_since(week_start)

    daily_loss_pct = (-daily_pnl / total_capital) * 100 if daily_pnl < 0 else 0
    weekly_loss_pct = (-weekly_pnl / total_capital) * 100 if weekly_pnl < 0 else 0

    if daily_loss_pct >= max_daily_loss_pct:
        return {
            "blocked": True,
            "severity": "DAILY_LOSS_LIMIT",
            "reason": f"Today's realized loss ({daily_loss_pct:.2f}%) has reached the "
                      f"{max_daily_loss_pct}% daily limit. New positions blocked for today.",
            "daily_pnl": round(daily_pnl, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
        }

    if weekly_loss_pct >= max_weekly_loss_pct:
        return {
            "blocked": True,
            "severity": "WEEKLY_LOSS_LIMIT",
            "reason": f"This week's realized loss ({weekly_loss_pct:.2f}%) has reached the "
                      f"{max_weekly_loss_pct}% weekly limit. New positions blocked this week.",
            "weekly_pnl": round(weekly_pnl, 2),
            "weekly_loss_pct": round(weekly_loss_pct, 2),
        }

    return {
        "blocked": False,
        "severity": "NORMAL",
        "reason": "No loss threshold breached.",
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss_pct": round(daily_loss_pct, 2),
        "weekly_pnl": round(weekly_pnl, 2),
        "weekly_loss_pct": round(weekly_loss_pct, 2),
    }