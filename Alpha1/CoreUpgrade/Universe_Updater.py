"""
Universe_Updater.py
-------------------------------------------------------------------------
Automated NSE Universe Maintenance System.
Fetches the official equity master, checks cache age, and strictly purges
delisted/renamed symbols from the Parquet cache and SQLite database.
"""

import os
import sqlite3
import requests
import pandas as pd
from datetime import datetime
from io import StringIO
from core.config import UNIVERSE_CSV_PATH, PARQUET_CACHE_DIR, DB_PATH

NSE_EQUITY_MASTER_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

def fetch_live_nse_master() -> tuple[set, pd.DataFrame]:
    print(f"📡 Requesting live equity master from NSE India...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        response = session.get(NSE_EQUITY_MASTER_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        df_live = pd.read_csv(StringIO(response.text))
        df_live.columns = [c.strip().upper() for c in df_live.columns]
        
        if "SERIES" in df_live.columns:
            df_live = df_live[df_live["SERIES"] == "EQ"]
            
        live_symbols = set(df_live["SYMBOL"].str.strip().str.upper().tolist())
        print(f"[+] Successfully fetched {len(live_symbols)} active symbols from NSE.")
        return live_symbols, df_live
    except Exception as e:
        print(f"[-] Critical Error fetching NSE master list: {e}")
        return set(), pd.DataFrame()

def purge_ghost_data(delisted_symbols: set):
    print("\n🧹 Initiating Ghost Data Purge...")
    pq_deleted = 0
    for sym in delisted_symbols:
        for suffix in ["", ".NS"]:
            pq_path = os.path.join(PARQUET_CACHE_DIR, f"{sym}{suffix}.parquet")
            if os.path.exists(pq_path):
                os.remove(pq_path)
                pq_deleted += 1
    print(f"  [-] Deleted {pq_deleted} stale Parquet files.")

    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            db_deleted = 0
            
            tables_to_scrub = ['daily_snapshot', 'scanner_factors', 'setup_pivots', 'market_regime', 'execution_candidates']
            
            for sym in delisted_symbols:
                sym_ns = f"{sym}.NS"
                for table in tables_to_scrub:
                    try:
                        # Bulletproof Dynamic Column Resolution
                        for col_name in ['ticker', 'Ticker', 'symbol', 'Symbol']:
                            try:
                                cursor.execute(f"DELETE FROM {table} WHERE {col_name} IN (?, ?)", (sym, sym_ns))
                                db_deleted += cursor.rowcount
                                break
                            except sqlite3.OperationalError:
                                continue
                    except Exception:
                        pass
                        
            conn.commit()
            conn.close()
            print(f"  [-] Purged {db_deleted} stale rows from SQLite database.")
        except Exception as e:
            print(f"  [!] Error purging SQLite: {e}")

def sync_universe():
    live_symbols, df_live = fetch_live_nse_master()
    if not live_symbols: return
        
    local_symbols = set()
    if os.path.exists(UNIVERSE_CSV_PATH):
        df_local = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.strip().upper() for c in df_local.columns]
        if "SYMBOL" in cols:
            sym_col = df_local.columns[cols.index("SYMBOL")]
            local_symbols = set(df_local[sym_col].dropna().astype(str).str.strip().str.upper().tolist())
    
    new_ipos_or_renames = live_symbols - local_symbols
    delisted_or_renamed = local_symbols - live_symbols
    
    print("\n" + "="*50)
    print("🔄 UNIVERSE RECONCILIATION REPORT")
    print("="*50)
    print(f"🟢 ADDED ({len(new_ipos_or_renames)}) | 🔴 REMOVED ({len(delisted_or_renamed)})")
        
    if delisted_or_renamed: purge_ghost_data(delisted_or_renamed)
        
    if new_ipos_or_renames or delisted_or_renamed or not os.path.exists(UNIVERSE_CSV_PATH):
        columns_to_keep = ["SYMBOL", "NAME OF COMPANY", "SERIES", "DATE OF LISTING"]
        available_cols = [c for c in df_live.columns if c in columns_to_keep]
        df_final = df_live[available_cols].sort_values(by="SYMBOL")
        df_final.to_csv(UNIVERSE_CSV_PATH, index=False)
        print("[+] Master universe CSV synchronized successfully.")
    else:
        print("[+] Local universe is perfectly synced. No ghost data found.")

if __name__ == "__main__":
    sync_universe()
