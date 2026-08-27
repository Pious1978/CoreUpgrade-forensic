"""
backfill_historical_snapshots.py
-------------------------------------------------------------------------
RESEARCH-GRADE HISTORICAL RECONSTRUCTION ENGINE (Fixed Boundary Errors)
"""

import os
import time
import pickle
import sqlite3
import datetime
import numpy as np
import pandas as pd
import yfinance as yf

from RS_Accel_Delivery_Trend import fetch_nse_delivery_report

# -------------------------------------------------------------------------
# PATH CONSTRAINTS & CORE SETTINGS
# -------------------------------------------------------------------------
BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest"
CSV_PATH = os.path.join(BASE_DIR, "nse_eq.csv")
DB_PATH = os.path.join(BASE_DIR, "rs_delivery_history.db")
CACHE_PATH = os.path.join(BASE_DIR, "backfill_price_cache.pkl")

WEEKS_BACK = 52          
REQUIRED_LOOKBACK_WEEKS = 53  # Safe buffer to prevent iloc[-53] crashes

def init_db_extended(db_path: str = DB_PATH):
    """Initializes standard storage tables with extended factor columns."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL,
            volume INTEGER,
            delivery_qty INTEGER,
            traded_qty INTEGER,
            delivery_pct REAL,
            rs_percentile REAL,
            ret_12m REAL,
            ret_6m REAL,
            ret_3m REAL,
            ret_1m REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()
    return conn

def load_symbols() -> list:
    df = pd.read_csv(CSV_PATH)
    cols = [c.upper().strip() for c in df.columns]
    symbol_col = df.columns[cols.index("SYMBOL")]
    raw = df[symbol_col].dropna().astype(str).tolist()
    clean = []
    for s in raw:
        s = s.strip().upper()
        if (s == "" or " " in s or "/" in s or "&" in s or "-" in s
                or s.startswith("DUMMY") or s.startswith("TEST")):
            continue
        clean.append(s + ".NS")
    return clean

def download_full_history(symbols: list, use_cache: bool = True) -> dict:
    """Downloads 2-year OHLCV records and returns resampled W-FRI arrays."""
    if use_cache and os.path.exists(CACHE_PATH):
        print(f"[*] Loading cached price history from {CACHE_PATH}")
        with open(CACHE_PATH, "rb") as f:
            return pickle.load(f)

    print(f"[*] Fetching 2y history for {len(symbols)} symbols from API...")
    price_history = {}
    for i, symbol in enumerate(symbols):
        try:
            df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
            time.sleep(0.02)
            if df is None or df.empty or len(df) < 100:
                continue
                
            close_series = df["Close"]
            if isinstance(close_series, pd.DataFrame):
                close_series = close_series.iloc[:, 0]
            
            weekly_series = close_series.dropna().resample("W-FRI").last().dropna()
            price_history[symbol] = weekly_series
        except Exception:
            continue

        if i % 200 == 0 and i > 0:
            print(f"    ...{i}/{len(symbols)} download steps completed")

    with open(CACHE_PATH, "wb") as f:
        pickle.dump(price_history, f)
    print(f"[+] Successfully cached {len(price_history)} tracking vectors.")
    return price_history

def _friday_dates(weeks_back: int) -> list:
    today = datetime.datetime.now()
    last_friday = today - datetime.timedelta(days=(today.weekday() - 4) % 7)
    return [last_friday - datetime.timedelta(weeks=w) for w in range(weeks_back, 0, -1)]

def backfill_rs_history(conn, price_history: dict, weeks_back: int = WEEKS_BACK):
    """
    Executes cross-sectional Point-In-Time Multi-Horizon Relative Strength scoring.
    Weights allocation matrix: 40% (12M), 20% (6M), 20% (3M), 20% (1M).
    """
    dates = _friday_dates(weeks_back)
    cur = conn.cursor()

    for d in dates:
        d_str = d.strftime("%Y-%m-%d")
        composite_scores_this_week = {}
        metrics_persistence_zone = {}

        for symbol, weekly_series in price_history.items():
            # Slice historical vectors strictly up to the current backfill date
            as_of_series = weekly_series[weekly_series.index <= d]
            
            # CRITICAL FIX: Ensure the sliced array has enough elements to perform the iloc[-53] lookup
            if len(as_of_series) < REQUIRED_LOOKBACK_WEEKS:
                continue

            # Standardized O'Neil lookback periods safely mapped via fixed index positions
            p_now = float(as_of_series.iloc[-1])
            p_4w  = float(as_of_series.iloc[-5])   # ~1 Month ago
            p_13w = float(as_of_series.iloc[-14])  # ~3 Months ago
            p_26w = float(as_of_series.iloc[-27])  # ~6 Months ago
            p_52w = float(as_of_series.iloc[-53])  # ~12 Months ago

            # Calculate returns per timeframe
            r_12m = (p_now - p_52w) / p_52w
            r_6m  = (p_now - p_26w) / p_26w
            r_3m  = (p_now - p_13w) / p_13w
            r_1m  = (p_now - p_4w) / p_4w

            # Core O'Neil / William O'Neil Formula Configuration
            composite_score = (0.4 * r_12m) + (0.2 * r_6m) + (0.2 * r_3m) + (0.2 * r_1m)
            
            clean_ticker = symbol.replace(".NS", "")
            composite_scores_this_week[clean_ticker] = composite_score
            
            metrics_persistence_zone[clean_ticker] = {
                "close": p_now,
                "r_12m": round(r_12m, 4),
                "r_6m": round(r_6m, 4),
                "r_3m": round(r_3m, 4),
                "r_1m": round(r_1m, 4)
            }

        if not composite_scores_this_week:
            continue

        # Rank all valid scores cross-sectionally for the current week context
        scores_series = pd.Series(composite_scores_this_week)
        rs_percentile_map = (scores_series.rank(pct=True) * 100).to_dict()

        for sym, rs_pct in rs_percentile_map.items():
            m = metrics_persistence_zone[sym]
            
            cur.execute("""
                INSERT INTO daily_snapshot
                    (symbol, date, close, volume, delivery_qty, traded_qty, delivery_pct, 
                     rs_percentile, ret_12m, ret_6m, ret_3m, ret_1m)
                VALUES (?, ?, ?, 0, 0, 0, NULL, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    close=excluded.close,
                    rs_percentile=excluded.rs_percentile,
                    ret_12m=excluded.ret_12m,
                    ret_6m=excluded.ret_6m,
                    ret_3m=excluded.ret_3m,
                    ret_1m=excluded.ret_1m
            """, (sym, d_str, m["close"], rs_pct, m["r_12m"], m["r_6m"], m["r_3m"], m["r_1m"]))

        conn.commit()
        print(f"[+] Integrated week: {d_str} | Evaluated {len(rs_percentile_map)} stocks.")

if __name__ == "__main__":
    symbols = load_symbols()
    
    # Leverages your existing cache file automatically if it exists
    price_history = download_full_history(symbols, use_cache=True)
    db_conn = init_db_extended(DB_PATH)
    
    print("\n[*] Initializing Multi-Horizon O'Neil Factor Backfill Routine...")
    backfill_rs_history(db_conn, price_history, weeks_back=WEEKS_BACK)
    
    print("\n[+] Reconstruction Complete. Database populated with research-grade historical snapshots.")
    db_conn.close()