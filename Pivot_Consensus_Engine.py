"""
Pivot_Consensus_Engine.py
-------------------------------------------------------------------------
Phase 3.5: Pivot Resolution
Resolves conflicting pivots across multiple scanners using structural hierarchy.
Outputs a clean `consensus_pivots` table for the Master Terminal to ingest.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime
from core.config import DB_PATH

PATTERN_HIERARCHY = {
    'Cup_and_Handle': 100,
    'Consolidation': 90,
    'Hybrid_Alpha': 85,
    'Emerging_Leader': 80,
    'Earnings_Gap': 75
}

def run_pivot_consensus():
    print("=" * 66)
    print("🎯 PIVOT CONSENSUS ENGINE")
    print("=" * 66)

    if not os.path.exists(DB_PATH): return

    conn = sqlite3.connect(DB_PATH)
    try:
        pivots_df = pd.read_sql("SELECT * FROM setup_pivots WHERE date = (SELECT MAX(date) FROM setup_pivots)", conn)
    except Exception:
        pivots_df = pd.DataFrame()

    if pivots_df.empty:
        print("[-] No structural pivots generated today. Exiting.")
        conn.close()
        return

    # Smart Pivot Resolution
    pivots_df['hierarchy_weight'] = pivots_df['source'].map(PATTERN_HIERARCHY).fillna(0)
    pivots_df = pivots_df.sort_values(by=['hierarchy_weight', 'confidence'], ascending=[False, False])
    resolved_pivots = pivots_df.drop_duplicates(subset=['ticker'], keep='first').copy()
    
    run_date = datetime.now().strftime("%Y-%m-%d")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consensus_pivots (
            ticker TEXT, pivot_price REAL, pattern TEXT, confidence REAL, date TEXT, 
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("DELETE FROM consensus_pivots WHERE date = ?", (run_date,))
    
    out_df = resolved_pivots[['ticker', 'pivot_price', 'source', 'confidence']].copy()
    out_df['date'] = run_date
    out_df.rename(columns={'source': 'pattern'}, inplace=True)
    
    out_df.to_sql('consensus_pivots', conn, if_exists='append', index=False)
    print(f"[*] Resolved optimal structural pivots for {len(out_df)} setups.")
    
    conn.commit()
    conn.close()
    print("=" * 66)

if __name__ == "__main__":
    run_pivot_consensus()
