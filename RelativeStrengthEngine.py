"""
RelativeStrengthEngine.py
-------------------------------------------------------------------------
Phase 1: Centralized Relative Strength & Delivery Engine
Computes cross-sectional RS percentiles and uses manual DB upserts to 
respect constraints safely.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

from core.config import DB_PATH, PARQUET_CACHE_DIR, MIN_TRADING_DAYS_RS, NIFTY_BENCHMARK_SYMBOL

def run_relative_strength_engine():
    print("=" * 70)
    print("📈 RELATIVE STRENGTH ENGINE")
    print("=" * 70)

    if not os.path.exists(PARQUET_CACHE_DIR):
        print(f"[-] Parquet cache directory not found at {PARQUET_CACHE_DIR}.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            symbol TEXT,
            date TEXT,
            close REAL,
            volume INTEGER,
            delivery_qty INTEGER,
            traded_qty INTEGER,
            delivery_pct REAL,
            rs_raw_return REAL,
            nifty_excess_return REAL,
            industry_relative_return REAL,
            rs_percentile REAL,
            rs_acceleration REAL,
            delivery_score REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()

    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet')]
    if not parquet_files:
        conn.close()
        return

    nifty_path = os.path.join(PARQUET_CACHE_DIR, f"{NIFTY_BENCHMARK_SYMBOL}.parquet")
    nifty_return = 0.0
    nifty_return_22d_ago = 0.0
    ACCEL_LOOKBACK_DAYS = 22

    if os.path.exists(nifty_path):
        ndf = pd.read_parquet(nifty_path)
        if len(ndf) >= 250:
            nifty_return = (float(ndf['close'].iloc[-1]) - float(ndf['close'].iloc[-250])) / float(ndf['close'].iloc[-250])
        if len(ndf) >= 250 + ACCEL_LOOKBACK_DAYS:
            price_22d_ago = float(ndf['close'].iloc[-1 - ACCEL_LOOKBACK_DAYS])
            price_272d_ago = float(ndf['close'].iloc[-1 - ACCEL_LOOKBACK_DAYS - 250])
            nifty_return_22d_ago = (price_22d_ago - price_272d_ago) / price_272d_ago if price_272d_ago > 0 else 0.0

    snapshot_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")

    for file in parquet_files:
        if "^NSEI" in file:
            continue
        symbol = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < MIN_TRADING_DAYS_RS:
                continue

            df.columns = [str(c).lower() for c in df.columns]
            latest_row = df.iloc[-1]
            close_val = float(latest_row['close'])
            vol_val = int(latest_row['volume'])
            deliv_qty = int(latest_row.get('delivery_qty', 0))
            traded_qty = int(latest_row.get('traded_qty', vol_val))
            deliv_pct = float(latest_row.get('delivery_pct', (deliv_qty / traded_qty * 100) if traded_qty > 0 else 0.0))

            start_close = float(df['close'].iloc[-250])
            rs_raw = (close_val - start_close) / start_close if start_close > 0 else 0.0

            # Real, working RS acceleration formula, confirmed in
            # Alpha1's hybrid_alpha_scanner1.py - the delta between
            # today's cross-sectional z-score of alpha and the same
            # z-score from 22 trading days ago, measuring whether a
            # stock's relative strength is genuinely accelerating or
            # decelerating, not just where it stands today. Directly
            # fills a field previously hardcoded to None - confirmed
            # empty across the board earlier tonight.
            excess_22d_ago = None
            if len(df) >= MIN_TRADING_DAYS_RS + ACCEL_LOOKBACK_DAYS:
                price_22d_ago = float(df['close'].iloc[-1 - ACCEL_LOOKBACK_DAYS])
                price_272d_ago = float(df['close'].iloc[-1 - ACCEL_LOOKBACK_DAYS - 250])
                rs_raw_22d_ago = (price_22d_ago - price_272d_ago) / price_272d_ago if price_272d_ago > 0 else None
                if rs_raw_22d_ago is not None:
                    excess_22d_ago = rs_raw_22d_ago - nifty_return_22d_ago

            snapshot_records.append({
                'symbol': symbol,
                'date': run_date,
                'close': close_val,
                'volume': vol_val,
                'delivery_qty': deliv_qty,
                'traded_qty': traded_qty,
                'delivery_pct': deliv_pct,
                'rs_raw_return': rs_raw,
                'nifty_excess_return': rs_raw - nifty_return,
                'nifty_excess_return_22d_ago': excess_22d_ago,
                'industry_relative_return': None
            })
        except Exception:
            continue

    if not snapshot_records:
        conn.close()
        return

    res_df = pd.DataFrame(snapshot_records)
    res_df['rs_percentile'] = res_df['rs_raw_return'].rank(method='average', pct=True) * 100.0

    # Real acceleration: z-score today's alpha and 22-days-ago's alpha
    # cross-sectionally (against this same universe snapshot), then take
    # the delta. Stocks missing a valid 22-days-ago value (genuinely
    # insufficient history) correctly get None rather than a fabricated
    # number - the z-score itself is computed only over stocks that do
    # have both values, so a handful of missing ones don't distort the
    # distribution for everyone else.
    valid_accel = res_df['nifty_excess_return_22d_ago'].notna()

    if valid_accel.sum() >= 30:
        z_today = (res_df.loc[valid_accel, 'nifty_excess_return'] - res_df.loc[valid_accel, 'nifty_excess_return'].mean()) / res_df.loc[valid_accel, 'nifty_excess_return'].std()
        z_22d_ago = (res_df.loc[valid_accel, 'nifty_excess_return_22d_ago'] - res_df.loc[valid_accel, 'nifty_excess_return_22d_ago'].mean()) / res_df.loc[valid_accel, 'nifty_excess_return_22d_ago'].std()
        res_df.loc[valid_accel, 'rs_acceleration'] = z_today - z_22d_ago

    if 'rs_acceleration' not in res_df.columns:
        res_df['rs_acceleration'] = None

    res_df['delivery_score'] = res_df['delivery_pct'].rank(method='average', pct=True) * 100.0

    output_cols = [
        'symbol', 'date', 'close', 'volume', 'delivery_qty', 'traded_qty', 
        'delivery_pct', 'rs_raw_return', 'nifty_excess_return', 
        'industry_relative_return', 'rs_percentile', 'rs_acceleration', 'delivery_score'
    ]
    
    print(f"[*] Upserting {len(res_df)} standardized RS metrics to SQLite...")
    cur = conn.cursor()
    for _, row in res_df[output_cols].iterrows():
        cur.execute("""
            INSERT INTO daily_snapshot (symbol, date, close, volume,
                delivery_qty, traded_qty, delivery_pct, rs_raw_return,
                nifty_excess_return, industry_relative_return,
                rs_percentile, rs_acceleration, delivery_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                close=excluded.close,
                volume=excluded.volume,
                delivery_pct=excluded.delivery_pct,
                rs_raw_return=excluded.rs_raw_return,
                nifty_excess_return=excluded.nifty_excess_return,
                rs_percentile=excluded.rs_percentile,
                delivery_score=excluded.delivery_score
        """, tuple(row[c] for c in output_cols))
    
    conn.commit()
    conn.close()
    print("[+] Baseline cross-sectional ranking complete.")

if __name__ == "__main__":
    run_relative_strength_engine()