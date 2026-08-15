"""
Cup_and_Handle.py
-------------------------------------------------------------------------
Factor Generator: Cup and Handle Scanner (Parquet-Native & Normalized)
Exports True Pattern Pivots and Confidence to SQLite for consensus.
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, MIN_PRICE, MIN_DAILY_TURNOVER

HANDLE_MIN_SESSIONS  = 5     
HANDLE_MAX_SESSIONS  = 30    
HANDLE_MIN_DEPTH     = 0.03  
HANDLE_MAX_DEPTH     = 0.15  
CUP_MIN_DEPTH        = 0.05  
CUP_MAX_DEPTH        = 0.35  
CUP_MIN_SESSIONS     = 20    

def _evaluate_cup(df: pd.DataFrame) -> dict:
    if len(df) < CUP_MIN_SESSIONS + HANDLE_MAX_SESSIONS: return None
    cup_window = df.iloc[-(252):-(HANDLE_MIN_SESSIONS)]
    if len(cup_window) < CUP_MIN_SESSIONS: return None

    left_rim_price  = float(cup_window['high'].iloc[:10].max())
    right_rim_price = float(cup_window['high'].iloc[-10:].max())
    cup_bottom      = float(cup_window['low'].min())

    rim_symmetry = abs(left_rim_price - right_rim_price) / max(left_rim_price, 1)
    if rim_symmetry > 0.08: return None

    higher_rim  = max(left_rim_price, right_rim_price)
    cup_depth   = (higher_rim - cup_bottom) / higher_rim
    if not (CUP_MIN_DEPTH <= cup_depth <= CUP_MAX_DEPTH): return None

    mid_start = len(cup_window) // 3
    mid_end   = 2 * len(cup_window) // 3
    mid_low   = float(cup_window['low'].iloc[mid_start:mid_end].mean())
    u_shape   = (mid_low - cup_bottom) / cup_bottom < 0.10

    depth_score    = max(0.0, 5.0 - abs(cup_depth - 0.20) * 20)
    symmetry_score = max(0.0, 2.0 - rim_symmetry * 20)
    shape_score    = 3.0 if u_shape else 1.0
    cup_score      = min(10.0, depth_score + symmetry_score + shape_score)

    return {'left_rim': left_rim_price, 'right_rim': right_rim_price, 'higher_rim': higher_rim,
            'cup_bottom': cup_bottom, 'cup_depth': cup_depth, 'cup_score': cup_score}

def _evaluate_handle(df: pd.DataFrame, cup: dict) -> dict:
    right_rim    = cup['right_rim']
    cup_bottom   = cup['cup_bottom']
    cup_midpoint = (right_rim + cup_bottom) / 2.0
    best_result, best_score = None, 0.0

    for handle_len in range(HANDLE_MIN_SESSIONS, HANDLE_MAX_SESSIONS + 1):
        if handle_len >= len(df): break
        handle = df.iloc[-handle_len:].copy()
        handle_high  = float(handle['high'].max())
        handle_low   = float(handle['low'].min())
        handle_close = float(handle['close'].iloc[-1])

        if handle_high > right_rim * 1.03: continue
        handle_depth = (right_rim - handle_low) / right_rim
        if not (HANDLE_MIN_DEPTH <= handle_depth <= HANDLE_MAX_DEPTH): continue
        if handle_low < cup_midpoint: continue
        
        drift_quality = (handle_close - handle_low) / max(handle_high - handle_low, 0.001)
        if drift_quality < 0.30: continue

        cup_window  = df.iloc[-(252 + handle_len):-(handle_len)]
        cup_avg_vol = float(cup_window['volume'].mean()) if not cup_window.empty else 1.0
        handle_avg_vol = float(handle['volume'].mean())
        vol_contraction = handle_avg_vol / cup_avg_vol if cup_avg_vol > 0 else 1.0

        first_half_vol  = float(handle['volume'].iloc[:handle_len//2].mean())
        second_half_vol = float(handle['volume'].iloc[handle_len//2:].mean())
        vol_drying      = second_half_vol < first_half_vol

        pivot = handle_high
        depth_pts     = max(0.0, min(6.0, 6.0 * (1.0 - abs(handle_depth - 0.08) / 0.08)))
        drift_pts     = min(3.0, drift_quality * 3.0)
        vol_pts       = 4.0 if (vol_contraction < 0.80 and vol_drying) else 2.0 if vol_contraction < 0.80 else 1.0 if vol_drying else 0.0
        duration_pts  = min(4.0, 4.0 * (1.0 - abs(handle_len - 12) / 18))

        handle_score = depth_pts + 3.0 + drift_pts + vol_pts + duration_pts
        if handle_score > best_score:
            best_score  = handle_score
            best_result = {'handle_len': handle_len, 'handle_high': handle_high, 'handle_low': handle_low,
                           'handle_depth': handle_depth, 'vol_contraction': round(vol_contraction, 2),
                           'vol_drying': vol_drying, 'pivot': pivot, 'handle_score': round(handle_score, 2)}
    return best_result

def _evaluate_volume_in_handle(handle: dict) -> float:
    if handle is None: return 0.0
    vol_score = 4.0 if (handle['vol_contraction'] < 0.70 and handle['vol_drying']) else 2.0 if handle['vol_contraction'] < 0.80 else 1.0 if handle['vol_drying'] else 0.0
    return min(8.0, vol_score * 2.0)

def run_cup_and_handle_scanner():
    print("=" * 60)
    print("☕ FACTOR GENERATOR: CUP & HANDLE SCANNER (v3 — True Pivot)")
    print("=" * 60)

    if not os.path.exists(PARQUET_CACHE_DIR): return
    parquet_files = [f for f in os.listdir(PARQUET_CACHE_DIR) if f.endswith('.parquet') and 'NSEI' not in f]
    
    factor_records = []
    pivot_records = []
    cups_found, handles_found, full_patterns = 0, 0, 0
    run_date = datetime.now().strftime("%Y-%m-%d")

    for file in parquet_files:
        ticker = file.replace('.parquet', '')
        path = os.path.join(PARQUET_CACHE_DIR, file)
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < 80: continue
            df.columns = [str(c).lower() for c in df.columns]
            
            latest_close = float(df['close'].iloc[-1])
            if latest_close < MIN_PRICE or (latest_close * float(df['volume'].iloc[-1]) < MIN_DAILY_TURNOVER): continue

            cup = _evaluate_cup(df)
            if cup is None: continue
            cups_found += 1

            handle = _evaluate_handle(df, cup)
            if handle is None:
                factor_records.append({'ticker': ticker, 'factor_name': 'cup_handle_quality', 'raw_val': cup['cup_score'] * 0.3, 'pattern_stage': 'CUP_ONLY'})
                continue

            handles_found += 1
            pivot = handle['pivot']
            pivot_dist = (pivot - latest_close) / pivot
            
            # Pattern Confidence Score (0-1)
            raw_confidence = (cup['cup_score'] + handle['handle_score'] + _evaluate_volume_in_handle(handle)) / 30.0

            if pivot_dist > 0.12:
                factor_records.append({'ticker': ticker, 'factor_name': 'cup_handle_quality', 'raw_val': raw_confidence * 0.8, 'pattern_stage': 'HANDLE_FORMING'})
                pivot_records.append({'ticker': ticker, 'pivot_price': pivot, 'source': 'Cup_and_Handle', 'confidence': raw_confidence * 0.8, 'date': run_date})
                continue

            full_patterns += 1
            factor_records.append({'ticker': ticker, 'factor_name': 'cup_handle_quality', 'raw_val': raw_confidence, 'pattern_stage': 'COMPLETE'})
            pivot_records.append({'ticker': ticker, 'pivot_price': pivot, 'source': 'Cup_and_Handle', 'confidence': raw_confidence, 'date': run_date})
        except Exception:
            continue

    if not factor_records: return

    # Save Factors
    factors_df = pd.DataFrame(factor_records)
    stage_rank = {'COMPLETE': 3, 'HANDLE_FORMING': 2, 'CUP_ONLY': 1}
    factors_df['stage_rank'] = factors_df['pattern_stage'].map(stage_rank).fillna(0)
    factors_df = factors_df.sort_values(['stage_rank', 'raw_val'], ascending=True).reset_index(drop=True)
    factors_df['score'] = (factors_df.index + 1) / len(factors_df)
    factors_df['date'] = run_date

    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS scanner_factors (ticker TEXT NOT NULL, factor_name TEXT NOT NULL, score REAL, date TEXT NOT NULL, PRIMARY KEY (ticker, factor_name, date))")
    conn.execute("DELETE FROM scanner_factors WHERE factor_name = 'cup_handle_quality' AND date = ?", (run_date,))
    factors_df[['ticker', 'factor_name', 'score', 'date']].to_sql('scanner_factors', conn, if_exists='append', index=False)
    
    # Save Pivots
    if pivot_records:
        conn.execute("CREATE TABLE IF NOT EXISTS setup_pivots (ticker TEXT, pivot_price REAL, source TEXT, confidence REAL, date TEXT, PRIMARY KEY (ticker, source, date))")
        conn.execute("DELETE FROM setup_pivots WHERE source = 'Cup_and_Handle' AND date = ?", (run_date,))
        pd.DataFrame(pivot_records).to_sql('setup_pivots', conn, if_exists='append', index=False)

    conn.commit()
    conn.close()
    
    print(f"[*] Cups detected        : {cups_found}")
    print(f"[*] Handles found        : {handles_found}")
    print(f"[*] Complete C&H patterns: {full_patterns}")
    print(f"[+] Wrote {len(factors_df)} factor points and {len(pivot_records)} true pivots to SQLite.")
    print("=" * 60)

if __name__ == "__main__":
    run_cup_and_handle_scanner()
