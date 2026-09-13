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


def check_recent_large_loss(total_capital, threshold_pct=1.5):
    """
    #85 - Real, direct feedback: "after a gap-down loss, stepping back
    rather than revenge-trading helps prevent compounding errors." This
    is a genuinely different signal from the existing daily/weekly
    aggregate thresholds above - a SINGLE abnormally large loss (e.g.
    a gap-through-stop) can be a warning sign worth a deliberate pause
    even when the aggregate daily/weekly loss hasn't hit its own
    threshold yet.

    Deliberately a WARNING, not a hard block like check_kill_switch()
    - a single bad trade is a behavioral nudge to step back and think,
    not necessarily a reason to halt all new sizing outright.

    Scoped to trades closed TODAY, since trade_journal's exit_date is
    date-only (no timestamp) - the finest real granularity available.
    """

    if total_capital <= 0:
        return {"warning": False, "reason": "Invalid capital for comparison."}

    try:
        conn = sqlite3.connect(DB_PATH)
        today = datetime.now().strftime("%Y-%m-%d")

        rows = conn.execute("""
            SELECT ticker, realized_pnl FROM trade_journal
            WHERE status = 'CLOSED' AND exit_date = ? AND realized_pnl < 0
        """, (today,)).fetchall()

        conn.close()

        for ticker, pnl in rows:
            loss_pct = (-pnl / total_capital) * 100
            if loss_pct >= threshold_pct:
                return {
                    "warning": True,
                    "ticker": ticker,
                    "loss_pct": round(loss_pct, 2),
                    "loss_amount": round(pnl, 2),
                    "reason": f"{ticker} closed today with a {loss_pct:.2f}% loss - a single, "
                              f"abnormally large loss. Consider stepping back before the next trade "
                              f"rather than immediately re-entering to make it back.",
                }

        return {"warning": False, "reason": "No single large loss detected today."}

    except Exception:
        return {"warning": False, "reason": "Unable to check - defaulting to no warning."}


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