"""
Earnings_Gap_Scanner.py
-------------------------------------------------------------------------
Factor Generator: Earnings Gap Scanner
Detects significant breakaway gaps with a 10-day lookback window for signal 
persistence, combining it with volume surge and storing in SQLite.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER, VOLUME_SMA_PERIOD

def run_earnings_gap_scanner():
    print("=" * 60)
    print("📊 FACTOR GENERATOR: EARNINGS GAP SCANNER (Corrected)")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR):
        return

    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet')]
    factor_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")

    for file in parquet_files:
        ticker = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < VOLUME_SMA_PERIOD + 15:
                continue

            df.columns = [str(c).lower() for c in df.columns]
            latest_close = float(df['close'].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df['volume'].iloc[-1])) < MIN_DAILY_TURNOVER:
                continue

            # Bug Fix: 10-day lookback window for signal persistence
            recent_11 = df.tail(11)
            gaps = (recent_11['open'] - recent_11['close'].shift(1)) / recent_11['close'].shift(1)
            max_gap_10d = gaps.clip(lower=0).max()

            vol_sma = df['volume'].rolling(window=VOLUME_SMA_PERIOD).mean().iloc[-1]
            latest_vol = float(df['volume'].iloc[-1])
            vol_surge = latest_vol / vol_sma if vol_sma > 0 else 1.0

            earnings_gap_strength = max_gap_10d * vol_surge

            factor_records.append({
                'ticker': ticker, 
                'factor_name': 'earnings_gap_strength', 
                'raw_val': earnings_gap_strength,
                'date': run_date
            })
        except Exception:
            continue

    if not factor_records:
        return

    factors_df = pd.DataFrame(factor_records)
    factors_df['score'] = factors_df['raw_val'].rank(method='average', pct=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scanner_factors (
            ticker TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            score REAL,
            date TEXT NOT NULL,
            PRIMARY KEY (ticker, factor_name, date)
        )
    """)
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'earnings_gap_strength' AND date = ?", (run_date,))
    conn.commit()

    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()

    print(f"[+] Wrote {len(factors_df)} normalized Earnings Gap factor points to SQLite.")

if __name__ == "__main__":
    run_earnings_gap_scanner()
