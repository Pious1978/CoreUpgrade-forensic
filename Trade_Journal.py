"""
Trade_Journal.py
------------------------------------------------------------
Alert -> Executed? -> Exit -> Return -> Reason -> Statistics

Tracks the full lifecycle of every trade candidate the pipeline
generates, so that after enough trades you have real, objective
evidence of which setups actually work - not just intuition.

There is no broker connection in this system, so "executed" and
"exit" are logged by you, honestly, not detected automatically.
The value of this tool depends entirely on logging consistently,
including trades you decided to skip.
"""

import sqlite3
from datetime import datetime

from core.config import DB_PATH


def init_journal_db():

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        pattern TEXT,
        alert_date TEXT,
        planned_pivot REAL,
        planned_stop REAL,
        planned_target_1 REAL,
        planned_target_2 REAL,
        planned_shares INTEGER,
        status TEXT,
        entry_price REAL,
        entry_date TEXT,
        entry_shares INTEGER,
        exit_price REAL,
        exit_date TEXT,
        exit_shares INTEGER,
        realized_pnl REAL,
        realized_pct REAL,
        r_multiple REAL,
        reason TEXT
    )
    """)

    conn.commit()
    conn.close()


def sync_alerts():
    """
    Pulls today's trade_candidates into trade_journal as new ALERTED
    rows. Safe to run multiple times a day - won't create duplicate
    alerts for the same ticker on the same date.
    """

    conn = sqlite3.connect(DB_PATH)

    candidates = conn.execute("""
        SELECT ticker, pattern, pivot, stop_loss, target_1, target_2, shares, date
        FROM trade_candidates
    """).fetchall()

    added = 0

    for ticker, pattern, pivot, stop, t1, t2, shares, date in candidates:

        existing = conn.execute(
            "SELECT id FROM trade_journal WHERE ticker=? AND alert_date=?",
            (ticker, date)
        ).fetchone()

        if existing:
            continue

        conn.execute("""
            INSERT INTO trade_journal
            (ticker, pattern, alert_date, planned_pivot, planned_stop,
             planned_target_1, planned_target_2, planned_shares, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ALERTED')
        """, (ticker, pattern, date, pivot, stop, t1, t2, shares))

        added += 1

    conn.commit()
    conn.close()

    print(f"[+] Synced {added} new alert(s) into the journal.")


def log_execution():

    conn = sqlite3.connect(DB_PATH)

    open_alerts = conn.execute("""
        SELECT id, ticker, alert_date, planned_pivot, planned_stop, planned_shares
        FROM trade_journal WHERE status='ALERTED'
        ORDER BY alert_date DESC
    """).fetchall()

    if not open_alerts:
        print("No un-actioned alerts to log.")
        conn.close()
        return

    print("\nUn-actioned alerts:")
    for row in open_alerts:
        print(f"  [{row[0]}] {row[1]} | alerted {row[2]} | pivot {row[3]} | stop {row[4]} | planned qty {row[5]}")

    try:
        journal_id = int(input("\nEnter the [id] of the trade you took: ").strip())
    except ValueError:
        print("Invalid id.")
        conn.close()
        return

    match = next((r for r in open_alerts if r[0] == journal_id), None)
    if not match:
        print("That id isn't in the un-actioned list.")
        conn.close()
        return

    try:
        entry_price = float(input("Actual entry price (Rs): ").strip())
        entry_shares = int(input("Actual quantity bought: ").strip())
    except ValueError:
        print("Invalid number.")
        conn.close()
        return

    entry_date = datetime.now().strftime("%Y-%m-%d")

    conn.execute("""
        UPDATE trade_journal
        SET status='EXECUTED', entry_price=?, entry_date=?, entry_shares=?
        WHERE id=?
    """, (entry_price, entry_date, entry_shares, journal_id))

    conn.commit()
    conn.close()

    print(f"[+] Logged execution for {match[1]}.")


def log_exit():

    conn = sqlite3.connect(DB_PATH)

    open_positions = conn.execute("""
        SELECT id, ticker, entry_price, entry_shares, planned_stop
        FROM trade_journal WHERE status='EXECUTED'
        ORDER BY entry_date DESC
    """).fetchall()

    if not open_positions:
        print("No open positions to close.")
        conn.close()
        return

    print("\nOpen positions:")
    for row in open_positions:
        print(f"  [{row[0]}] {row[1]} | entry {row[2]} | qty {row[3]}")

    try:
        journal_id = int(input("\nEnter the [id] of the position you closed: ").strip())
    except ValueError:
        print("Invalid id.")
        conn.close()
        return

    match = next((r for r in open_positions if r[0] == journal_id), None)
    if not match:
        print("That id isn't in the open positions list.")
        conn.close()
        return

    _, ticker, entry_price, entry_shares, planned_stop = match

    try:
        exit_price = float(input("Exit price (Rs): ").strip())
        exit_shares = int(input(f"Quantity sold (default {entry_shares}): ").strip() or entry_shares)
    except ValueError:
        print("Invalid number.")
        conn.close()
        return

    reason = input("Reason (why you exited - hit target, stopped out, changed mind, etc.): ").strip()

    planned_risk_per_share = entry_price - planned_stop
    realized_pnl_per_share = exit_price - entry_price

    r_multiple = (
        round(realized_pnl_per_share / planned_risk_per_share, 2)
        if planned_risk_per_share > 0 else None
    )

    realized_pnl = round(realized_pnl_per_share * exit_shares, 2)
    realized_pct = round((realized_pnl_per_share / entry_price) * 100, 2)

    exit_date = datetime.now().strftime("%Y-%m-%d")

    conn.execute("""
        UPDATE trade_journal
        SET status='CLOSED', exit_price=?, exit_date=?, exit_shares=?,
            realized_pnl=?, realized_pct=?, r_multiple=?, reason=?
        WHERE id=?
    """, (exit_price, exit_date, exit_shares, realized_pnl, realized_pct, r_multiple, reason, journal_id))

    conn.commit()
    conn.close()

    print(f"[+] Closed {ticker}: Rs {realized_pnl} ({realized_pct}%, {r_multiple}R)")


def show_open_positions():

    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute("""
        SELECT ticker, entry_date, entry_price, entry_shares, planned_stop, planned_target_1, planned_target_2
        FROM trade_journal WHERE status='EXECUTED'
        ORDER BY entry_date DESC
    """).fetchall()

    conn.close()

    if not rows:
        print("No open positions.")
        return

    print(f"\n{'Ticker':<12}{'Entry Date':<12}{'Entry':<9}{'Qty':<6}{'Stop':<9}{'T1':<9}{'T2':<9}")
    print("-" * 66)
    for r in rows:
        print(f"{r[0]:<12}{r[1]:<12}{r[2]:<9.2f}{r[3]:<6}{r[4]:<9.2f}{r[5]:<9.2f}{r[6]:<9.2f}")


def show_statistics():

    conn = sqlite3.connect(DB_PATH)

    closed = conn.execute("""
        SELECT ticker, pattern, realized_pnl, realized_pct, r_multiple, reason
        FROM trade_journal WHERE status='CLOSED'
    """).fetchall()

    conn.close()

    if not closed:
        print("No closed trades yet - statistics need at least a few closed trades to mean anything.")
        return

    total = len(closed)
    wins = [c for c in closed if c[2] is not None and c[2] > 0]
    losses = [c for c in closed if c[2] is not None and c[2] <= 0]

    win_rate = round(len(wins) / total * 100, 1)

    r_values = [c[4] for c in closed if c[4] is not None]
    avg_r = round(sum(r_values) / len(r_values), 2) if r_values else None

    total_pnl = round(sum(c[2] for c in closed if c[2] is not None), 2)

    print(f"\n{'='*50}")
    print(f"TRADE JOURNAL STATISTICS ({total} closed trades)")
    print(f"{'='*50}")
    print(f"Win rate       : {win_rate}% ({len(wins)}W / {len(losses)}L)")
    print(f"Average R      : {avg_r}R" if avg_r is not None else "Average R      : N/A")
    print(f"Total P&L      : Rs {total_pnl}")

    # Breakdown by pattern - which setups are actually working
    patterns = {}
    for c in closed:
        p = c[1] or "UNKNOWN"
        patterns.setdefault(p, []).append(c[4])

    print(f"\nBy pattern:")
    for p, rs in patterns.items():
        valid_rs = [r for r in rs if r is not None]
        avg = round(sum(valid_rs) / len(valid_rs), 2) if valid_rs else "N/A"
        print(f"  {p:<20} {len(rs)} trades, avg {avg}R")

    print(f"{'='*50}")


def main_menu():

    init_journal_db()

    while True:

        print("\n" + "="*50)
        print("TRADE JOURNAL")
        print("="*50)
        print("1. Sync today's alerts")
        print("2. Log an execution (I took this trade)")
        print("3. Log an exit (I closed this position)")
        print("4. Show open positions")
        print("5. Show statistics")
        print("6. Exit")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            sync_alerts()
        elif choice == "2":
            log_execution()
        elif choice == "3":
            log_exit()
        elif choice == "4":
            show_open_positions()
        elif choice == "5":
            show_statistics()
        elif choice == "6":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main_menu()