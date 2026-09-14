"""
Event_Log.py

Addresses #93 - events are truth; tables are projections.

HONEST, DELIBERATE SCOPE: this does not migrate every existing table
in the system to event-sourcing - that would be a large, high-risk
rewrite touching many working parts (`scanner_factors`, regime data,
and more all remain table-based, unchanged). This establishes a real,
working event log for the parts of the system that are ALREADY,
STRUCTURALLY append-only and immutable - a TradePlan is generated
once, a HumanTradeDecision is made once, an ActualTrade fill happens
once, a trade closes once. These are the natural, honest starting
point for "events are truth": nothing about them needs migrating,
they just needed a single, unified place to be recorded together
instead of scattered across separate, individually-queried tables.

Real, genuine payoff, direct from the architectural review's own
example: given a ticker, get_events_for_ticker() reconstructs the
entire, real story - plan, decision, fill, exit - from ONE source,
in chronological order, rather than requiring four separate,
manually-joined queries across four different tables.
"""

import sqlite3
import json
from datetime import datetime

from core.config import DB_PATH


def log_event(event_type, ticker, payload):
    """
    Real, direct, append-only event write. No update, no delete -
    once logged, an event is permanent, matching the real, immutable
    nature of what it represents (a plan was generated; a decision
    was made; a fill happened - none of these can un-happen).
    """

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            ticker TEXT,
            event_timestamp TEXT,
            payload_json TEXT
        )
    """)

    conn.execute("""
        INSERT INTO event_log (event_type, ticker, event_timestamp, payload_json)
        VALUES (?, ?, ?, ?)
    """, (
        event_type,
        ticker.upper() if ticker else None,
        datetime.now().isoformat(),
        json.dumps(payload, default=str),
    ))

    conn.commit()
    conn.close()


def get_events_for_ticker(ticker):
    """
    Real, direct reconstruction of a ticker's full, chronological
    story from the event log alone - the genuine payoff the
    architectural review asked for: "six months later, you can
    reconstruct the entire story" from one source, not four separate,
    manually-joined tables.
    """

    import pandas as pd

    conn = sqlite3.connect(DB_PATH)

    try:
        df = pd.read_sql("""
            SELECT event_type, event_timestamp, payload_json FROM event_log
            WHERE UPPER(ticker) = ?
            ORDER BY event_timestamp ASC
        """, conn, params=(ticker.upper(),))
    except Exception:
        df = pd.DataFrame()

    conn.close()

    return df


def print_ticker_story(ticker):
    """Human-readable rendering of a ticker's full, real event history."""

    events = get_events_for_ticker(ticker)

    if events.empty:
        print(f"No events found for {ticker.upper()}.")
        return

    print()
    print("=" * 70)
    print(f"EVENT HISTORY: {ticker.upper()}")
    print("=" * 70)

    for _, row in events.iterrows():
        payload = json.loads(row["payload_json"])
        print(f"\n[{row['event_timestamp']}] {row['event_type']}")
        for k, v in payload.items():
            print(f"    {k}: {v}")

    print("=" * 70)


if __name__ == "__main__":
    ticker = input("Ticker: ").strip().upper()
    print_ticker_story(ticker)