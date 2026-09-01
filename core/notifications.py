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
"""

import sqlite3
import os
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


def send_alert(event_type, ticker, severity, message):
    """
    Real, single entry point for every notification-worthy event.
    Deduplicates automatically - safe to call every monitoring cycle,
    only the first call per (ticker, event_type) per day actually
    produces output.

    severity: "INFO", "WARNING", or "CRITICAL" - purely for the log
    output's visual weight, doesn't change delivery.
    """

    init_alert_log_table()

    if already_alerted_today(ticker, event_type):
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{severity}] [{event_type}] {ticker}: {message}\n"

    with open(ALERT_LOG_PATH, "a") as f:
        f.write(line)

    mark_alerted(ticker, event_type)

    return True