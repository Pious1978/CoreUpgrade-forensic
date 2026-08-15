"""
Confirmation_Factor_Generator.py
-------------------------------------------------------------------------
Factor Generator: Volume Confirmation & Pivot Proximity Scanner

Computes true weekly RVOL, intraday RVOL, and pivot extension factors 
from yesterday's EOD data. Runs as a standard Layer 3 batch process.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

from core.config import (
    PARQUET_CACHE_DIR, 
    DB_PATH, 
    PIVOT_BUFFER_PCT, 
    VOLUME_SMA_PERIOD
)

def run_confirmation_scanner():
    print("=" * 60)
    print("✅ FACTOR GENERATOR: CONFIRMATION FACTORS")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR):
        print(f"[-] Parquet cache not found at {PARQUET_CACHE_DIR}")
        return

    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet')]
    factor_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")
    processed_count = 0

    for file in parquet_files:
        ticker = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < 50:
                continue

            df.columns = [str(c).lower() for c in df.columns]
            if not all(c in df.columns for c in ['close', 'high', 'low', 'volume', 'date']):
                continue

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            latest_close = float(df['close'].iloc[-1])
            latest_vol = float(df['volume'].iloc[-1])
            vol_sma = df['volume'].rolling(window=VOLUME_SMA_PERIOD).mean().iloc[-1]
            intraday_rvol = latest_vol / vol_sma if vol_sma > 0 else 1.0

            df_weekly = df.resample('W').agg({'volume': 'sum'}).dropna()
            if len(df_weekly) >= 10:
                weekly_vol_sma = df_weekly['volume'].rolling(window=10).mean().iloc[-1]
                latest_weekly_vol = float(df_weekly['volume'].iloc[-1])
                weekly_rvol = latest_weekly_vol / weekly_vol_sma if weekly_vol_sma > 0 else 1.0
            else:
                weekly_rvol = intraday_rvol

            resistance_20d = df['high'].iloc[-21:-1].max() if len(df) >= 21 else latest_close
            trigger_price = resistance_20d * (1.0 + PIVOT_BUFFER_PCT / 100.0)

            extension = (latest_close - trigger_price) / trigger_price
            extension_score = max(0.0, 1.0 - abs(extension))

            factor_records.append({'ticker': ticker, 'factor_name': 'intraday_rvol', 'raw_val': intraday_rvol, 'date': run_date})
            factor_records.append({'ticker': ticker, 'factor_name': 'weekly_rvol', 'raw_val': weekly_rvol, 'date': run_date})
            factor_records.append({'ticker': ticker, 'factor_name': 'pivot_extension', 'raw_val': extension_score, 'date': run_date})
            
            processed_count += 1
            
        except Exception:
            continue

    if not factor_records:
        print("[-] No confirmation factors generated.")
        return

    factors_df = pd.DataFrame(factor_records)
    factors_df['score'] = factors_df.groupby('factor_name')['raw_val'].transform(lambda x: x.rank(method='average', pct=True))

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
    conn.execute("DELETE FROM scanner_factors WHERE factor_name IN ('intraday_rvol', 'weekly_rvol', 'pivot_extension') AND date = ?", (run_date,))
    conn.commit()

    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()
    
    print(f"[+] Wrote confirmation factors for {processed_count} tickers to SQLite.")
    print("=" * 60)

if __name__ == "__main__":
    run_confirmation_scanner()
