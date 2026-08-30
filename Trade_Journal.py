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
import os
import pandas as pd
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

    # A position can now be exited in more than one tranche (e.g. sell
    # half at T1, trail the rest to T2) - each exit is its own row here,
    # rather than overwriting a single exit_price/exit_shares column on
    # trade_journal, which could only ever represent one final exit.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_journal_exits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journal_id INTEGER,
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


def get_remaining_shares(conn, journal_id, entry_shares):
    """
    Entry shares minus everything already exited (across one or more
    partial exits) against this specific position.
    """

    exited = conn.execute(
        "SELECT COALESCE(SUM(exit_shares), 0) FROM trade_journal_exits WHERE journal_id=?",
        (journal_id,)
    ).fetchone()[0]

    return entry_shares - exited


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


def log_manual_entry():
    """
    For a trade this system never alerted on - a past purchase, something
    you found through your own research, or anything bought before this
    pipeline existed. Creates a new position directly as EXECUTED, rather
    than requiring it to have started as an ALERTED row from
    sync_alerts(). Stop/target are optional here - Live_Execution_Monitor.py
    already handles a missing stop/target gracefully (shows "no stop on
    file, monitor manually" instead of breaking).
    """

    conn = sqlite3.connect(DB_PATH)

    ticker = input("Ticker: ").strip().upper()

    if not ticker:
        print("Ticker can't be empty.")
        conn.close()
        return

    try:
        entry_price = float(input("Entry price (Rs): ").strip())
        entry_shares = int(input("Quantity bought: ").strip())
    except ValueError:
        print("Invalid number.")
        conn.close()
        return

    entry_date_input = input("Entry date (YYYY-MM-DD, blank for today): ").strip()
    entry_date = entry_date_input if entry_date_input else datetime.now().strftime("%Y-%m-%d")

    pattern = input("Pattern/reason for the trade (optional, e.g. 'Own research'): ").strip() or "MANUAL"

    stop_input = input("Planned stop-loss (Rs, blank if none): ").strip()
    t1_input = input("Target 1 (Rs, blank if none): ").strip()
    t2_input = input("Target 2 (Rs, blank if none): ").strip()

    try:
        planned_stop = float(stop_input) if stop_input else 0.0
        planned_target_1 = float(t1_input) if t1_input else 0.0
        planned_target_2 = float(t2_input) if t2_input else 0.0
    except ValueError:
        print("Invalid number for stop/target.")
        conn.close()
        return

    conn.execute("""
        INSERT INTO trade_journal
        (ticker, pattern, alert_date, planned_pivot, planned_stop,
         planned_target_1, planned_target_2, planned_shares, status,
         entry_price, entry_date, entry_shares)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'EXECUTED', ?, ?, ?)
    """, (
        ticker, pattern, entry_date, entry_price, planned_stop,
        planned_target_1, planned_target_2, entry_shares,
        entry_price, entry_date, entry_shares
    ))

    conn.commit()
    conn.close()

    print(f"[+] Logged manual entry for {ticker}: {entry_shares} shares at Rs{entry_price} on {entry_date}.")


def load_portfolio_csv(file_path):
    """
    Reads a broker-exported holdings CSV - adapted from Alpha1's real,
    working portfolio_loader.py. Doesn't assume one fixed broker's
    export format; searches for keyword patterns in column names
    instead (STOCK/SYMBOL/INSTRUMENT/SECURITY/TRADING for the ticker,
    QTY/QUANTITY for quantity, PRICE/AVG/COST for average price), so it
    should work across different brokers' exports, not just one.
    """

    if not os.path.exists(file_path):
        print(f"[-] File not found: {file_path}")
        return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])

    try:
        df = pd.read_csv(file_path)

        # Some broker exports have a title row before the real header
        if df.shape[1] == 1:
            df = pd.read_csv(file_path, skiprows=1)

        print(f"[*] Detected columns: {list(df.columns)}")

        stock_col = qty_col = price_col = None

        for col in df.columns:
            col_upper = str(col).upper()

            if stock_col is None and any(x in col_upper for x in ["STOCK", "SYMBOL", "INSTRUMENT", "SECURITY", "TRADING"]):
                stock_col = col

            if qty_col is None and any(x in col_upper for x in ["QTY", "QUANTITY"]):
                qty_col = col

            if price_col is None and any(x in col_upper for x in ["PRICE", "AVG", "COST"]):
                price_col = col

        if stock_col is None:
            print("[-] Could not detect a stock/symbol column automatically.")
            return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])

        print(f"[+] Using columns - Stock: {stock_col}, Qty: {qty_col or 'not found, defaulting to 0'}, "
              f"Price: {price_col or 'not found, defaulting to 0'}")

        df_out = pd.DataFrame()
        df_out["Stock"] = df[stock_col].astype(str).str.upper().str.strip()
        df_out["Qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0) if qty_col else 0
        df_out["AvgPrice"] = pd.to_numeric(df[price_col], errors="coerce").fillna(0) if price_col else 0

        df_out = df_out[(df_out["Stock"] != "NAN") & (df_out["Stock"] != "")]
        df_out = df_out.drop_duplicates(subset=["Stock"], keep="last")
        df_out = df_out.reset_index(drop=True)

        return df_out

    except Exception as e:
        print(f"[-] Error loading portfolio CSV: {e}")
        return pd.DataFrame(columns=["Stock", "Qty", "AvgPrice"])


def log_bulk_import():
    """
    Bulk-imports your entire current portfolio from a broker-exported
    holdings CSV in one shot - complements log_manual_entry()'s
    one-at-a-time entry. Real, honest limitation: broker exports
    typically don't include the original entry date, so it defaults to
    today - correct manually afterward if you know the real date and it
    matters to you (e.g. for hold-period tracking).
    """

    file_path = input("Path to your broker holdings CSV: ").strip()

    portfolio = load_portfolio_csv(file_path)

    if portfolio.empty:
        print("[-] No holdings found to import.")
        return

    print(f"\n[*] Found {len(portfolio)} holdings in the file:")
    for _, row in portfolio.iterrows():
        print(f"  {row['Stock']}: {row['Qty']} shares @ Rs{row['AvgPrice']}")

    confirm = input(f"\nImport all {len(portfolio)} positions? (y/n): ").strip().lower()

    if confirm != "y":
        print("Cancelled - nothing imported.")
        return

    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")

    imported = 0
    skipped = 0

    for _, row in portfolio.iterrows():

        ticker = row["Stock"]
        qty = int(row["Qty"])
        avg_price = float(row["AvgPrice"])

        if qty <= 0 or avg_price <= 0:
            print(f"  [-] Skipping {ticker} - invalid quantity or price in the file.")
            skipped += 1
            continue

        existing = conn.execute(
            "SELECT COUNT(*) FROM trade_journal WHERE UPPER(ticker)=? AND status='EXECUTED'",
            (ticker,)
        ).fetchone()[0]

        if existing:
            print(f"  [-] Skipping {ticker} - already logged as an open position.")
            skipped += 1
            continue

        conn.execute("""
            INSERT INTO trade_journal
            (ticker, pattern, alert_date, planned_pivot, planned_stop,
             planned_target_1, planned_target_2, planned_shares, status,
             entry_price, entry_date, entry_shares)
            VALUES (?, 'BROKER_IMPORT', ?, ?, 0, 0, 0, ?, 'EXECUTED', ?, ?, ?)
        """, (ticker, today, avg_price, qty, avg_price, today, qty))

        imported += 1

    conn.commit()
    conn.close()

    print(f"\n[+] Imported {imported} positions, skipped {skipped}.")

    if imported > 0:
        print("[*] Entry date defaulted to today since broker exports don't include the "
              "original entry date - correct manually if you know the real date.")


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

    # Show REMAINING shares, not the original entry_shares - a position
    # may already have had a partial exit logged against it.
    print("\nOpen positions:")
    remaining_map = {}
    for row in open_positions:
        journal_id, ticker, entry_price, entry_shares, planned_stop = row
        remaining = get_remaining_shares(conn, journal_id, entry_shares)
        remaining_map[journal_id] = remaining
        print(f"  [{journal_id}] {ticker} | entry {entry_price} | remaining qty {remaining} (of {entry_shares} original)")

    try:
        journal_id = int(input("\nEnter the [id] of the position you're exiting (fully or partially): ").strip())
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
    remaining = remaining_map[journal_id]

    try:
        exit_price = float(input("Exit price (Rs): ").strip())
        exit_shares = int(input(f"Quantity sold (default {remaining}, your full remaining position): ").strip() or remaining)
    except ValueError:
        print("Invalid number.")
        conn.close()
        return

    if exit_shares <= 0 or exit_shares > remaining:
        print(f"Invalid quantity - must be between 1 and {remaining} (your remaining position).")
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
        INSERT INTO trade_journal_exits
        (journal_id, exit_price, exit_date, exit_shares, realized_pnl, realized_pct, r_multiple, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (journal_id, exit_price, exit_date, exit_shares, realized_pnl, realized_pct, r_multiple, reason))

    new_remaining = remaining - exit_shares

    if new_remaining <= 0:

        # Fully closed now - also populate the legacy single-exit columns
        # on trade_journal itself, for anything that still reads them
        # directly, using this final exit's values.
        conn.execute("""
            UPDATE trade_journal
            SET status='CLOSED', exit_price=?, exit_date=?, exit_shares=?,
                realized_pnl=?, realized_pct=?, r_multiple=?, reason=?
            WHERE id=?
        """, (exit_price, exit_date, exit_shares, realized_pnl, realized_pct, r_multiple, reason, journal_id))

        print(f"[+] Closed {ticker} (final exit): Rs {realized_pnl} ({realized_pct}%, {r_multiple}R)")

    else:

        print(f"[+] Partial exit for {ticker}: sold {exit_shares}, Rs {realized_pnl} ({realized_pct}%, {r_multiple}R). {new_remaining} shares remain open.")

    conn.commit()
    conn.close()


def show_open_positions():

    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute("""
        SELECT id, ticker, entry_date, entry_price, entry_shares, planned_stop, planned_target_1, planned_target_2
        FROM trade_journal WHERE status='EXECUTED'
        ORDER BY entry_date DESC
    """).fetchall()

    if not rows:
        print("No open positions.")
        conn.close()
        return

    print(f"\n{'Ticker':<12}{'Entry Date':<12}{'Entry':<9}{'Qty':<6}{'Stop':<9}{'T1':<9}{'T2':<9}")
    print("-" * 66)
    for r in rows:
        journal_id, ticker, entry_date, entry_price, entry_shares, stop, t1, t2 = r
        remaining = get_remaining_shares(conn, journal_id, entry_shares)
        print(f"{ticker:<12}{entry_date:<12}{entry_price:<9.2f}{remaining:<6}{stop:<9.2f}{t1:<9.2f}{t2:<9.2f}")

    conn.close()


def show_statistics():

    conn = sqlite3.connect(DB_PATH)

    # Every exit event counts toward statistics as soon as it happens -
    # not just fully-closed positions. A partial exit at T1 is real,
    # already-realized P&L, and shouldn't stay invisible to statistics
    # until the rest of the position eventually closes too.
    closed = conn.execute("""
        SELECT tj.ticker, tj.pattern, te.realized_pnl, te.realized_pct, te.r_multiple, te.reason
        FROM trade_journal_exits te
        JOIN trade_journal tj ON tj.id = te.journal_id
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
        print("6. Log a manual/past entry (not from an alert)")
        print("7. Bulk-import your portfolio from a broker CSV")
        print("8. Exit")

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
            log_manual_entry()
        elif choice == "7":
            log_bulk_import()
        elif choice == "8":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main_menu()