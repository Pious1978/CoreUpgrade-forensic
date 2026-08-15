"""
Hybrid_Alpha_Scanner.py
-------------------------------------------------------------------------
Factor Generator: Hybrid Alpha & VCP (Volatility Contraction) Scanner
Detects multi-stage volatility contraction, extracts true structural breakout 
pivots, and exports confidence scores to the Execution Consensus Engine.
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER

# VCP & Hybrid Alpha Constraints
VCP_MIN_DAYS = 30
VCP_MAX_DAYS = 90
MIN_CONFIDENCE = 0.45

def _evaluate_vcp(df: pd.DataFrame) -> dict:
    """
    Evaluates Volatility Contraction Patterns (VCP) by measuring successional 
    declines in price volatility and volume across sub-windows of the base.
    """
    if len(df) < VCP_MAX_DAYS: return None

    base_df = df.iloc[-VCP_MAX_DAYS:].copy()
    
    # Divide the base into 3 contraction sub-phases (e.g., 30 days each)
    n = len(base_df)
    third = n // 3
    
    phase1 = base_df.iloc[:third]
    phase2 = base_df.iloc[third:2*third]
    phase3 = base_df.iloc[2*third:]
    
    # Measure volatility (Standard Deviation of daily returns) for each phase
    v1 = float(phase1['close'].pct_change().std() * 100)
    v2 = float(phase2['close'].pct_change().std() * 100)
    v3 = float(phase3['close'].pct_change().std() * 100)
    
    # True VCP shows progressive volatility contraction (v1 > v2 > v3)
    is_contracting = (v1 > v2) and (v2 > v3)
    if not is_contracting:
        # Allow a looser check if phase 2 and 3 are both low volatility
        if v3 > v1 * 0.8: return None

    # Resistance Pivot (Highest high of the tightening phase / right side)
    right_side = base_df.iloc[third:]
    pivot_price = float(right_side['high'].max())
    base_low = float(base_df['low'].min())
    curr_px = float(df['close'].iloc[-1])
    
    # Ensure current price is within striking distance of the pivot and above base low
    if curr_px < base_low * 0.95 or curr_px > pivot_price * 1.08: return None
    
    # Volume Contraction Check
    vol_left = float(phase1['volume'].mean())
    vol_right = float(phase3['volume'].mean())
    vol_drying = vol_right < vol_left
    
    # Scoring components
    volatility_score = max(0.0, 1.0 - (v3 / (v1 + 1e-8)))
    depth_score = max(0.0, 1.0 - ((pivot_price - base_low) / pivot_price))
    vol_score = 1.0 if vol_drying else 0.5
    
    confidence = (volatility_score * 0.45) + (depth_score * 0.35) + (vol_score * 0.20)
    if confidence < MIN_CONFIDENCE: return None

    return {
        'pivot': pivot_price,
        'confidence': confidence,
        'vol_contraction_ratio': v3 / (v1 + 1e-8),
        'depth': (pivot_price - base_low) / pivot_price
    }

def run_hybrid_alpha_scanner():
    print("=" * 60)
    print("🧬 FACTOR GENERATOR: HYBRID ALPHA / VCP SCANNER (True Pivot)")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR): return
    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet') and 'NSEI' not in f]
    
    factor_records = []
    pivot_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")
    vcp_count = 0

    for file in parquet_files:
        ticker = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < VCP_MAX_DAYS: continue
            df.columns = [str(c).lower() for c in df.columns]
            
            latest_close = float(df['close'].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df['volume'].iloc[-1]) < MIN_DAILY_TURNOVER): continue

            vcp = _evaluate_vcp(df)
            if vcp is None:
                factor_records.append({'ticker': ticker, 'factor_name': 'hybrid_alpha_score', 'raw_val': 0.0})
                continue
            
            vcp_count += 1

            # 1. Record Factor Score
            factor_records.append({
                'ticker': ticker, 
                'factor_name': 'hybrid_alpha_score', 
                'raw_val': vcp['confidence']
            })
            
            # 2. Record True Execution Pivot
            pivot_records.append({
                'ticker': ticker, 
                'pivot_price': vcp['pivot'], 
                'source': 'Hybrid_Alpha', 
                'confidence': vcp['confidence'], 
                'date': run_date
            })
            
        except Exception:
            continue

    if not factor_records: return

    # Normalize Factors (0.0 to 1.0 percentile ranking)
    factors_df = pd.DataFrame(factor_records)
    factors_df = factors_df.sort_values('raw_val', ascending=True).reset_index(drop=True)
    factors_df['score'] = factors_df['raw_val'].rank(pct=True)
    factors_df['date'] = run_date

    # Database Writes
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Write to scanner_factors
    conn.execute("CREATE TABLE IF NOT EXISTS scanner_factors (ticker TEXT NOT NULL, factor_name TEXT NOT NULL, score REAL, date TEXT NOT NULL, PRIMARY KEY (ticker, factor_name, date))")
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'hybrid_alpha_score' AND date = ?", (run_date,))
    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    
    # 2. Write True Pivots to setup_pivots
    if pivot_records:
        conn.execute("CREATE TABLE IF NOT EXISTS setup_pivots (ticker TEXT, pivot_price REAL, source TEXT, confidence REAL, date TEXT, PRIMARY KEY (ticker, source, date))")
        conn.execute("DELETE FROM setup_pivots WHERE source = 'Hybrid_Alpha' AND date = ?", (run_date,))
        pd.DataFrame(pivot_records).to_sql('setup_pivots', conn, if_exists='append', index=False)

    conn.commit()
    conn.close()
    
    print(f"[*] VCP / Hybrid Setups Detected : {vcp_count}")
    print(f"[+] Wrote {len(factors_df)} factor points and {len(pivot_records)} true pivots to SQLite.")
    print("=" * 60)

if __name__ == "__main__":
    run_hybrid_alpha_scanner()
