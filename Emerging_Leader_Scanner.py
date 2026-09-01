"""
Emerging_Leader_Scanner.py
-------------------------------------------------------------------------
Factor Generator: Emerging Leader Scanner
Computes 20-session accumulation ratio correctly and normalizes scores to SQLite.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER


def _evaluate_accumulation(df: pd.DataFrame) -> float:
    """
    Pure, real accumulation-ratio calculation, extracted from
    run_emerging_leader_scanner()'s own inline logic - "same logic,
    reusable form," not a second implementation. Takes only a
    DataFrame, returns the raw ratio (0.0-1.0). The live function below
    now calls this directly; behavior is identical to before.
    """

    recent = df.tail(20)
    up_days = recent[recent["close"] > recent["close"].shift(1)]["volume"].sum()
    total_vol = recent["volume"].sum()
    return up_days / total_vol if total_vol > 0 else 0.5


def run_emerging_leader_scanner():
    print("=" * 60)
    print("🌱 FACTOR GENERATOR: EMERGING LEADER SCANNER (Corrected)")
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
            if df.empty or len(df) < 50:
                continue

            df.columns = [str(c).lower() for c in df.columns]
            latest_close = float(df['close'].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df['volume'].iloc[-1])) < MIN_DAILY_TURNOVER:
                continue

            accum_ratio = _evaluate_accumulation(df)

            factor_records.append({'ticker': ticker, 'factor_name': 'accumulation_ratio', 'raw_val': accum_ratio, 'date': run_date})
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
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'accumulation_ratio' AND date = ?", (run_date,))
    conn.commit()

    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()

    print(f"[+] Wrote {len(factors_df)} Emerging Leader factor points to SQLite.")

if __name__ == "__main__":
    run_emerging_leader_scanner()