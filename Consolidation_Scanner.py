"""
Consolidation_Scanner.py
-------------------------------------------------------------------------
Factor Generator: Consolidation & Flat Base Scanner
Detects tight bases, calculates the true geometric resistance (Pivot), 
and exports structural confidence to the Execution Consensus Engine.
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER

# Institutional constraints for a Flat Base / Consolidation Box
BASE_MIN_DAYS = 15
BASE_MAX_DAYS = 65
MAX_BASE_DEPTH = 0.25      # Base should not correct more than 25% from its high
MIN_CONFIDENCE = 0.40      # Minimum structural confidence to register a pivot

def _evaluate_consolidation(df: pd.DataFrame) -> dict:
    """
    Scans multiple time windows (15 to 65 days) to find the mathematically 
    tightest consolidation base and its true structural resistance pivot.
    """
    if len(df) < BASE_MAX_DAYS: return None

    best_score = 0.0
    best_base = None

    # Test multiple structural windows to find the most coherent base
    for window in [15, 21, 30, 40, 50, 65]:
        if window > len(df): continue
        
        base_df = df.iloc[-window:]
        base_high = float(base_df['high'].max())
        base_low = float(base_df['low'].min())
        
        if base_high <= 0: continue
        
        depth = (base_high - base_low) / base_high
        if depth > MAX_BASE_DEPTH: continue
        
        # Volume contraction analysis (Second half vs First half of the base)
        half = window // 2
        vol_1 = float(base_df['volume'].iloc[:half].mean())
        vol_2 = float(base_df['volume'].iloc[half:].mean())
        vol_contraction = vol_2 / vol_1 if vol_1 > 0 else 1.0
        
        # Ensure price hasn't already broken down or blown out completely
        curr_px = float(df['close'].iloc[-1])
        if curr_px < base_low * 0.98 or curr_px > base_high * 1.05: continue
        
        # Structural Confidence Scoring (0.0 to 1.0)
        # 1. Depth Score (Tighter is exponentially better)
        depth_score = max(0.0, 1.0 - (depth / MAX_BASE_DEPTH))
        # 2. Volume Score (Drying volume on the right side of the base is bullish)
        vol_score = max(0.0, 1.0 - vol_contraction) if vol_contraction < 1.0 else 0.0
        # 3. Duration Score (Reward longer bases up to 40 days)
        len_score = min(1.0, window / 40.0)
        
        # Weighted Confidence
        raw_confidence = (depth_score * 0.50) + (vol_score * 0.30) + (len_score * 0.20)
        
        if raw_confidence > best_score:
            best_score = raw_confidence
            best_base = {
                'pivot': base_high,
                'depth': depth,
                'length': window,
                'vol_contraction': vol_contraction,
                'confidence': raw_confidence
            }
            
    return best_base

def run_consolidation_scanner():
    print("=" * 60)
    print("🏭 FACTOR GENERATOR: CONSOLIDATION SCANNER (True Pivot)")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR): return
    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet') and 'NSEI' not in f]
    
    factor_records = []
    pivot_records = []
    run_date = datetime.now().strftime("%Y-%m-%d")
    
    bases_found = 0
    tight_flags = 0

    for file in parquet_files:
        ticker = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < BASE_MAX_DAYS: continue
            df.columns = [str(c).lower() for c in df.columns]
            
            latest_close = float(df['close'].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df['volume'].iloc[-1]) < MIN_DAILY_TURNOVER): continue

            base = _evaluate_consolidation(df)
            if base is None or base['confidence'] < MIN_CONFIDENCE: 
                # Output a zero-score factor to maintain coverage math
                factor_records.append({'ticker': ticker, 'factor_name': 'base_compression', 'raw_val': 0.0})
                continue
            
            bases_found += 1
            if base['depth'] <= 0.10 and base['length'] <= 21:
                tight_flags += 1
                pattern_name = 'Tight_Flag'
            else:
                pattern_name = 'Consolidation'

            # 1. Record Research Factors
            factor_records.append({
                'ticker': ticker, 
                'factor_name': 'base_compression', 
                'raw_val': base['confidence']
            })
            
            # 2. Record True Execution Pivot
            pivot_records.append({
                'ticker': ticker, 
                'pivot_price': base['pivot'], 
                'source': pattern_name, 
                'confidence': base['confidence'], 
                'date': run_date
            })
            
        except Exception:
            continue

    if not factor_records: return

    # Normalize Factors (Cross-sectional ranking 0.0 to 1.0)
    factors_df = pd.DataFrame(factor_records)
    factors_df = factors_df.sort_values('raw_val', ascending=True).reset_index(drop=True)
    factors_df['score'] = factors_df['raw_val'].rank(pct=True)
    factors_df['date'] = run_date

    # Database Writes
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Write to scanner_factors
    conn.execute("CREATE TABLE IF NOT EXISTS scanner_factors (ticker TEXT NOT NULL, factor_name TEXT NOT NULL, score REAL, date TEXT NOT NULL, PRIMARY KEY (ticker, factor_name, date))")
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'base_compression' AND date = ?", (run_date,))
    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    
    # 2. Write True Pivots to setup_pivots
    if pivot_records:
        conn.execute("CREATE TABLE IF NOT EXISTS setup_pivots (ticker TEXT, pivot_price REAL, source TEXT, confidence REAL, date TEXT, PRIMARY KEY (ticker, source, date))")
        conn.execute("DELETE FROM setup_pivots WHERE source IN ('Consolidation', 'Tight_Flag') AND date = ?", (run_date,))
        pd.DataFrame(pivot_records).to_sql('setup_pivots', conn, if_exists='append', index=False)

    conn.commit()
    conn.close()
    
    print(f"[*] Standard Consolidations : {bases_found - tight_flags}")
    print(f"[*] High Tight Flags        : {tight_flags}")
    print(f"[+] Wrote {len(factors_df)} factor points and {len(pivot_records)} true pivots to SQLite.")
    print("=" * 60)

if __name__ == "__main__":
    run_consolidation_scanner()
