"""
core/notifications.py

#56 - Real notifications, via a reusable boundary rather than
hardwired into individual scanners/monitors - any caller sends a
normalized event through send_alert(); this module owns
deduplication, formatting, and the output channel.

Channel: local log file (SwingBacktest-style dedicated file), matching
the "local alert/log" channel from the plan's design - the simplest,
most reliable channel, with zero external dependencies or credentials
needed. Email/Telegram can be added as additional channel adapters
later without changing any caller.

Deduplication: the same (ticker, event_type) pair only alerts once per
day - critical given Live_Execution_Monitor.py refreshes continuously;
without this, a stock sitting in VALID_BREAKOUT would re-alert every
single cycle.

RICHER CONTEXT (added following direct analysis of the first two
weeks of real alerts.log data): that analysis found a real, honest
limitation - alerts.log only ever recorded RVOL, so no multi-factor
analysis was possible, and worse, matching a later TARGET_1_HIT back
to "the" earlier VALID_BREAKOUT for the same ticker was genuinely
ambiguous for 27% of tickers, which had multiple, separate breakout
attempts over the period.

Two real, direct fixes:
1. send_alert() now accepts optional pattern/score/breakout_id kwargs
   and writes them as a structured " | key=value" suffix - parseable,
   backward-compatible (old lines without the suffix still parse fine
   for ticker/event_type/timestamp).
2. A new active_breakout_id table tracks, per ticker, the id of its
   current, still-open breakout. A VALID_BREAKOUT call generates a new
   id and registers it; TARGET_1_HIT/TARGET_2_HIT/STOP_BREACHED calls
   look up and include that same id, so a later outcome can be
   unambiguously traced back to the exact breakout that produced it -
   no more matching by ticker name and timestamp ordering alone.
"""

import sqlite3
import os
import hashlib
from datetime import datetime

from core.config import DB_PATH

ALERT_LOG_PATH = "alerts.log"


def init_alert_log_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_dedup_log (
            ticker TEXT, event_type TEXT, alert_date TEXT,
            PRIMARY KEY (ticker, event_type, alert_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_breakout_id (
            ticker TEXT PRIMARY KEY,
            breakout_id TEXT,
            pattern TEXT,
            score REAL
        )
    """)
    conn.commit()
    conn.close()


def already_alerted_today(ticker, event_type):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(
        "SELECT 1 FROM alert_dedup_log WHERE ticker=? AND event_type=? AND alert_date=?",
        (ticker, event_type, today)
    ).fetchone()
    conn.close()
    return result is not None


def mark_alerted(ticker, event_type):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO alert_dedup_log (ticker, event_type, alert_date) VALUES (?, ?, ?)",
        (ticker, event_type, today)
    )
    conn.commit()
    conn.close()


def register_new_breakout(ticker, pattern, score):
    """
    Real, direct registration of a new breakout's identity, called when
    VALID_BREAKOUT fires. Replaces any prior entry for this ticker -
    a new breakout genuinely supersedes an earlier one, which is either
    already resolved or itself ambiguous at that point.
    """

    init_alert_log_table()

    breakout_id = hashlib.sha1(f"{ticker}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO active_breakout_id (ticker, breakout_id, pattern, score) VALUES (?, ?, ?, ?)",
        (ticker, breakout_id, pattern, score)
    )
    conn.commit()
    conn.close()

    return breakout_id


def get_active_breakout(ticker):
    """
    Real, direct lookup of a ticker's current, still-open breakout
    identity - used by TARGET_1_HIT/TARGET_2_HIT/STOP_BREACHED to
    unambiguously reference which breakout produced this outcome.
    Returns None honestly if no breakout was ever registered for this
    ticker (e.g. a position opened before this tracking existed).
    """

    init_alert_log_table()

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT breakout_id, pattern, score FROM active_breakout_id WHERE ticker=?",
        (ticker,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {"breakout_id": row[0], "pattern": row[1], "score": row[2]}


def send_alert(event_type, ticker, severity, message, pattern=None, score=None, breakout_id=None):
    """
    Real, single entry point for every notification-worthy event.
    Deduplicates automatically - safe to call every monitoring cycle,
    only the first call per (ticker, event_type) per day actually
    produces output.

    severity: "INFO", "WARNING", or "CRITICAL" - purely for the log
    output's visual weight, doesn't change delivery.

    pattern/score/breakout_id: optional, real richer context (see
    module docstring) - written as a structured, parseable suffix.
    Omitted entirely (not even the suffix) when not provided, so old
    parsing code and old log lines both remain valid.
    """

    init_alert_log_table()

    if already_alerted_today(ticker, event_type):
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{severity}] [{event_type}] {ticker}: {message}"

    context_parts = []
    if breakout_id is not None:
        context_parts.append(f"breakout_id={breakout_id}")
    if pattern is not None:
        context_parts.append(f"pattern={pattern}")
    if score is not None:
        context_parts.append(f"score={score}")

    if context_parts:
        line += " | " + " ".join(context_parts)

    line += "\n"

    with open(ALERT_LOG_PATH, "a") as f:
        f.write(line)

    mark_alerted(ticker, event_type)

    return True