"""
Event_Decline_Scanner.py

Event-anchored decline scanner - adapted from Alpha1's real
corrected_month.py ("Market Crash Detector" / "Bloodhound for
Discounts" per your own Script Tracker.txt notes). Answers a genuinely
different question from Bear_Market_Scanner.py: not "who's fallen from
their own 52-week high" (a rolling, always-on metric), but "who's
fallen the most since a specific date I choose" - useful for a known
event (a market-wide correction, a specific news day, a sector shock)
where you want to see who actually got hit hardest since then.

Genuine improvement over the original script: uses our own real,
backfilled parquet_cache instead of a live yfinance bulk download - no
live network dependency, and fully usable right now (purely
price-based, unlike the recent Monday-gated fundamentals work).
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, UNIVERSE_CSV_PATH, BASE_DIR
from core.excel_utils import save_excel_with_retry


def load_universe():
    """Reuses the same NSE_EQ.csv universe file every other scanner in
    this pipeline already relies on, for consistency."""

    try:
        df = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            print("[-] SYMBOL column missing from universe file.")
            return []

        symbol_col = df.columns[cols.index("SYMBOL")]
        symbols = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()

        return sorted(set(s for s in symbols if len(s) >= 2))

    except Exception as e:
        print(f"[-] Error loading universe: {e}")
        return []


def find_anchor_price(df, anchor_date):
    """
    Finds the closest available trading date ON OR AFTER the requested
    anchor date - handles weekends/holidays gracefully rather than
    requiring an exact match, since the user's chosen date might not
    have been a trading day.
    """

    df_after = df[df.index >= anchor_date]

    if df_after.empty:
        return None, None

    actual_date = df_after.index[0]
    return float(df_after["close"].iloc[0]), actual_date


def analyze_decline(ticker, anchor_date):
    """
    Real decline calculation from our own backfilled parquet_cache - no
    live data needed at all, unlike the original script's live yfinance
    bulk download.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # Only drop rows missing the price data this needs - a blanket
        # dropna() would also drop backfilled rows missing
        # delivery_qty/delivery_pct (intentionally NULL for Yahoo-
        # sourced history). Same real bug found and fixed in
        # Market_Regime_Engine.py, Bear_Market_Scanner.py, and
        # Compounder_Scanner.py.
        df = df.dropna(subset=["close"])

        if df.empty:
            return None

        anchor_price, actual_anchor_date = find_anchor_price(df, anchor_date)

        if anchor_price is None or anchor_price <= 0:
            return None

        current_price = float(df["close"].iloc[-1])
        current_date = df.index[-1]

        pct_change = ((current_price - anchor_price) / anchor_price) * 100

        return {
            "ticker": ticker,
            "anchor_date": actual_anchor_date.strftime("%Y-%m-%d"),
            "anchor_price": round(anchor_price, 2),
            "current_date": current_date.strftime("%Y-%m-%d"),
            "current_price": round(current_price, 2),
            "pct_change": round(pct_change, 2),
        }

    except Exception:
        return None


def run(anchor_date_str=None, drop_threshold=-12.0):

    print()
    print("=" * 70)
    print("EVENT DECLINE SCANNER")
    print("=" * 70)

    if anchor_date_str is None:
        anchor_date_str = input("Anchor date to measure decline from (YYYY-MM-DD): ").strip()

    try:
        anchor_date = pd.Timestamp(anchor_date_str)
    except Exception:
        print(f"[-] Invalid date: {anchor_date_str}")
        return

    if drop_threshold is None:
        threshold_input = input("Minimum decline % to flag (e.g. 12 for -12%, blank for default 12): ").strip()
        drop_threshold = -abs(float(threshold_input)) if threshold_input else -12.0

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    print(f"[*] Scanning {len(symbols)} stocks for a decline of {abs(drop_threshold)}% "
          f"or more since {anchor_date.date()}...")

    declined_stocks = []

    for symbol in symbols:
        result = analyze_decline(symbol, anchor_date)
        if result and result["pct_change"] <= drop_threshold:
            declined_stocks.append(result)

    if not declined_stocks:
        print(f"\n[+] No stocks found down {abs(drop_threshold)}% or more since {anchor_date.date()}.")
        return

    result_df = pd.DataFrame(declined_stocks).sort_values("pct_change")

    today = datetime.now().strftime("%Y-%m-%d")
    result_df["scan_date"] = today

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_decline_scans (
            ticker TEXT,
            anchor_date TEXT,
            anchor_price REAL,
            current_date TEXT,
            current_price REAL,
            pct_change REAL,
            scan_date TEXT
        )
    """)
    conn.execute("DELETE FROM event_decline_scans WHERE anchor_date = ? AND scan_date = ?",
                 (anchor_date.strftime("%Y-%m-%d"), today))
    result_df.to_sql("event_decline_scans", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, f"EVENT_DECLINE_{anchor_date.strftime('%Y%m%d')}.xlsx")
    save_excel_with_retry(result_df, excel_path, index=False)

    print(f"\n[+] Found {len(result_df)} stocks down {abs(drop_threshold)}% or more "
          f"since {anchor_date.date()}:")
    print(result_df.to_string(index=False))
    print(f"\n[+] Written to event_decline_scans and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()