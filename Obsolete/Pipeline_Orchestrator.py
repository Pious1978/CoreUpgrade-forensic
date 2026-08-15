"""
Pipeline_Orchestrator.py
-------------------------------------------------------------------------
Master execution DAG. Initializes strict unified database schemas to 
prevent SQLite IntegrityErrors, then orchestrates the daily batch sequence
using isolated subprocesses to guarantee memory safety.
"""

import os
import sqlite3
import subprocess
import sys
from core.config import DB_PATH

STAGES = [
    "Universe_Updater.py",
    "Market_Data_Cache.py",
    "RelativeStrengthEngine.py",
    "Market_Regime_Engine.py",
    "Consolidation_Scanner.py",
    "Hybrid_Alpha_Scanner.py",
    "Emerging_Leader_Scanner.py",
    "Earnings_Gap_Scanner.py",
    "Cup_and_Handle.py",
    "Master_Terminal.py"
]

def initialize_central_database():
    """Forces all SQLite tables to use the exact correct schemas before any scanner runs."""
    print("[*] Initializing Central Database Schemas...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # 💥 FORCE WIPE THE OLD SCHEMAS (Prevents ghost columns) 💥
    conn.execute("DROP TABLE IF EXISTS scanner_factors")
    conn.execute("DROP TABLE IF EXISTS daily_snapshot")
    conn.execute("DROP TABLE IF EXISTS market_regime")
    # We deliberately leave cache_metadata alone so you don't have to re-download Parquet files

    # 1. Daily Snapshot (RS Engine)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            symbol TEXT, date TEXT, close REAL, volume INTEGER,
            delivery_qty INTEGER, traded_qty INTEGER, delivery_pct REAL,
            rs_raw_return REAL, nifty_excess_return REAL,
            industry_relative_return REAL, rs_percentile REAL,
            rs_acceleration REAL, delivery_score REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    
    # 2. Scanner Factors (UNIFIED 3-COLUMN KEY FOR ALL SCANNERS)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scanner_factors (
            ticker TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            score REAL,
            date TEXT NOT NULL,
            PRIMARY KEY (ticker, factor_name, date)
        )
    """)
    
    # 3. Market Regime
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_regime (
            date TEXT PRIMARY KEY,
            breadth_50 REAL, breadth_200 REAL,
            regime TEXT, total_stocks INTEGER
        )
    """)
    
    # 4. Cache Metadata (Ensures it exists if missing)
    conn.execute("CREATE TABLE IF NOT EXISTS cache_metadata (last_updated TEXT)")
    
    conn.commit()
    conn.close()
    print("[+] Database schemas strictly enforced (Old schemas purged).")

def run_pipeline():
    print("=" * 70)
    print("🚀 QUANTITATIVE ALPHA PIPELINE (DAILY BATCH)")
    print("=" * 70)
    
    # Lock in schemas first
    initialize_central_database()
    
    # Run the DAG execution sequence
    for stage in STAGES:
        print(f"\n{'-' * 70}")
        print(f"⏳ RUNNING STAGE: {stage}")
        print(f"{'-' * 70}")
        
        result = subprocess.run([sys.executable, stage])
        
        if result.returncode != 0:
            print(f"\n[-] CRITICAL ERROR: {stage} failed with code {result.returncode}.")
            print("[-] Halting pipeline to prevent data corruption downstream.")
            sys.exit(1)
            
    print("\n" + "=" * 70)
    print("✅ DAILY BATCH PIPELINE COMPLETE.")
    print("All institutional setups have been ranked and persisted.")
    print("You may now launch Breakout_Trigger_Scanner.py for live execution mode.")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline()
