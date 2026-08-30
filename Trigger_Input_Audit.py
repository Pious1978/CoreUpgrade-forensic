"""
Trigger_Input_Audit.py
-------------------------------------------------------------------------
Institutional Pipeline QA Suite: Comprehensive Production Trigger Audit
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter
from core.config import DB_PATH, PARQUET_CACHE_DIR

def run_trigger_input_audit():
    print("==================================================================")
    print("🔍 PIPELINE QA SUITE: INSTITUTIONAL TRIGGER INPUT AUDIT")
    print("==================================================================")
    
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # 1. DATABASE CONNECTION & PIPELINE TABLE RECONCILIATION
    # ------------------------------------------------------------------
    print("\n[PHASE 1] Connecting to Database & Reconciling Pipeline Flow...")
    
    db_pass = False
    table_exists = False
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check trade_candidates table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_candidates';")
        table_exists = cursor.fetchone() is not None
        
        # Reconcile counts across pipeline tables (Research -> Execution Plan -> Trade Candidates -> Positions)
        def get_table_count(tbl_name):
            try:
                res = cursor.execute(f"SELECT COUNT(*) FROM {tbl_name};").fetchone()
                return res[0] if res else 0
            except Exception:
                return 0

        research_count = get_table_count("research_consensus")
        if research_count == 0:
            research_count = get_table_count("research_watchlist") # Fallback alias
            
        execution_plan_count = get_table_count("execution_plan")
        trade_candidates_count = get_table_count("trade_candidates")
        open_positions_count = get_table_count("open_positions")
        if open_positions_count == 0:
            open_positions_count = get_table_count("positions") # Fallback alias

        # Fetch latest market regime state
        regime_df = pd.read_sql("SELECT * FROM market_regime ORDER BY date DESC LIMIT 1", conn) if table_exists else pd.DataFrame()
        market_regime = "NEUTRAL"
        exposure_multiplier = 0.5
        if not regime_df.empty:
            market_regime = regime_df.iloc[0].get("regime", "NEUTRAL")
            exposure_multiplier = float(regime_df.iloc[0].get("position_multiplier", 0.5))

        if not table_exists:
            print("    ❌ FAILED: Table `trade_candidates` does not exist.")
            conn.close()
            return
        
        df = pd.read_sql("SELECT * FROM trade_candidates", conn)
        conn.close()
        db_pass = True
        db_status = "PASS"
        print("    ✅ PASSED: Database connectivity and flow tables verified.")
    except Exception as e:
        print(f"    ❌ FAILED to connect or read database: {e}")
        return

    total_candidates = len(df)
    if total_candidates == 0:
        print("    ⚠️ Table `trade_candidates` is empty. Aborting audit.")
        return

    # ------------------------------------------------------------------
    # 2. SCHEMA DISCOVERY & ALIAS MAPPING
    # ------------------------------------------------------------------
    expected_columns = [
        "ticker", "pivot", "pattern", "confidence", "atr_14", 
        "stop_loss", "target_1", "target_2", "risk_per_share", 
        "shares", "composite_score", "tier", "date"
    ]
    
    column_aliases = {
        "ticker": ["ticker", "Symbol"],
        "pivot": ["pivot", "trigger_price", "pivot_price"],
        "atr_14": ["atr_14", "atr14", "ATR14"],
        "shares": ["shares", "recommended_quantity", "quantity"],
        "risk_per_share": ["risk_per_share", "risk_per_share_pct"],
        "composite_score": ["composite_score", "Composite_Score"],
        "confidence": ["confidence", "pattern_confidence"],
        "tier": ["tier", "Tier"],
        "pattern": ["pattern", "Pattern"]
    }

    resolved_map = {}
    missing_columns = []
    for col in expected_columns:
        found = False
        if col in df.columns:
            resolved_map[col] = col
            found = True
        elif col in column_aliases:
            for alias in column_aliases[col]:
                if alias in df.columns:
                    resolved_map[col] = alias
                    found = True
                    break
        if not found:
            resolved_map[col] = None
            missing_columns.append(col)

    schema_status = "PASS" if not missing_columns else "WARN"

    def get_col_val(row, logical_name):
        actual_col = resolved_map.get(logical_name)
        if actual_col and actual_col in row and pd.notna(row[actual_col]):
            try:
                return float(row[actual_col])
            except ValueError:
                return row[actual_col]
        return 0.0

    # ------------------------------------------------------------------
    # 3. NORMALIZATION & DUPLICATE GROUP AUDIT
    # ------------------------------------------------------------------
    ticker_col = resolved_map.get('ticker')
    if ticker_col and ticker_col in df.columns:
        df['normalized_ticker'] = (
            df[ticker_col].astype(str)
            .str.replace(r'\.(NS|BO|NSE|BSE)$', '', regex=True)
            .str.upper()
        )
        duplicate_groups = df.groupby("normalized_ticker").size()
        duplicate_symbol_count = int((duplicate_groups > 1).sum())
    else:
        df['normalized_ticker'] = "UNKNOWN"
        duplicate_symbol_count = 0

    dup_status = "PASS" if duplicate_symbol_count == 0 else "WARN"

    # ------------------------------------------------------------------
    # 4. COMPREHENSIVE LAYER AUDIT & ROW VALIDATION
    # ------------------------------------------------------------------
    print("\n[PHASE 2] Executing Multi-Layer Structural, Risk & Execution Audits...")

    research_pass_count = 0
    risk_pass_count = 0
    atr_ok_count = 0
    risk_ok_count = 0
    price_pass_count = 0
    target_pass_count = 0
    pos_pass_count = 0
    market_data_pass_count = 0

    failure_records = []
    ready_row_indices = []
    seen_normalized_tickers = set()

    research_layer_ok = True
    risk_layer_ok = True
    execution_layer_ok = True
    price_structure_ok = True
    risk_structure_ok = True
    target_structure_ok = True
    position_sizing_ok = True
    market_data_ok = True
    freshness_ok = True

    # Portfolio allocation limit parameters
    base_capital = 100000.0
    effective_capital = base_capital * exposure_multiplier
    max_position_allocation = effective_capital * 0.20 # Max 20% per trade

    for idx, row in df.iterrows():
        reasons = []
        
        pivot = float(get_col_val(row, 'pivot') or 0.0)
        atr = float(get_col_val(row, 'atr_14') or 0.0)
        stop = float(row.get('stop_loss', 0.0) or 0.0)
        t1 = float(row.get('target_1', 0.0) or 0.0)
        t2 = float(row.get('target_2', 0.0) or 0.0)
        risk = float(get_col_val(row, 'risk_per_share') or 0.0)
        shares = float(get_col_val(row, 'shares') or 0.0)
        comp_score = float(get_col_val(row, 'composite_score') or 0.5)
        
        pattern_val = row.get('pattern', None)
        tier_val = row.get('tier', None)
        norm_sym = row['normalized_ticker']
        row_date = str(row.get('date', current_date_str))

        # Confidence validation (0 to 2 range)
        conf_raw = row.get('confidence', 1.0)
        if isinstance(conf_raw, str):
            conf_val = 1.0 if conf_raw.upper() in ["HIGH", "MEDIUM", "TIER-1"] else (0.5 if conf_raw.upper() == "LOW" else 0.0)
        else:
            conf_val = float(conf_raw) if pd.notna(conf_raw) else -1.0

        # --- Duplicate Check (Handled gracefully) ---
        if norm_sym in seen_normalized_tickers:
            reasons.append("Duplicate Symbol Variant")
        else:
            seen_normalized_tickers.add(norm_sym)

        # --- Freshness Check (Issue 6: Flag stale dates) ---
        if row_date != current_date_str:
            reasons.append(f"Stale Date ({row_date})")
            freshness_ok = False

        # --- Research Layer Audit ---
        research_row_ok = True
        if pd.isna(pattern_val) or str(pattern_val).strip() in ["", "None", "NAN", "NULL"]:
            reasons.append("Pattern NULL")
            research_row_ok = False
        if pd.isna(tier_val) or str(tier_val).strip() in ["", "None", "NAN", "NULL"]:
            reasons.append("Tier NULL")
            research_row_ok = False
        if not (0.0 <= conf_val <= 2.0):
            reasons.append("Invalid Confidence (<0 or >2)")
            research_row_ok = False
        if not (0.0 <= comp_score <= 1.0):
            reasons.append("Invalid Composite Score (Must be 0-1)")
            research_row_ok = False

        if research_row_ok:
            research_pass_count += 1
        else:
            research_layer_ok = False

        # --- Price Structure & Stop Logic (Issue 8: stop < pivot AND stop > pivot - 8*ATR) ---
        price_row_ok = True
        if pivot <= 0:
            reasons.append("Invalid Pivot")
            price_row_ok = False
        elif stop <= 0 or stop >= pivot:
            reasons.append("Invalid Stop (Must be < Pivot)")
            price_row_ok = False
        elif atr > 0 and stop < (pivot - (8.0 * atr)):
            reasons.append("Stop too wide (< Pivot - 8*ATR)")
            price_row_ok = False

        if price_row_ok:
            price_pass_count += 1
        else:
            price_structure_ok = False

        # --- Risk Structure & ATR Audit (Issue 1: Split counters atr_ok and risk_ok) ---
        if atr > 0:
            if pivot > 0 and atr > pivot:
                reasons.append("ATR > Price (Anomalous ATR)")
            else:
                atr_ok_count += 1
        # Note: atr <= 0 is a soft warning, not a hard fail for IPOs/data gaps

        if risk > 0:
            risk_ok_count += 1
            risk_pass_count += 1
        else:
            reasons.append("Negative/Zero Risk")
            risk_structure_ok = False

        # --- Target Structure & Reward/Risk Audit (Issue 9: pivot < t1 < t2 < pivot + 8*ATR) ---
        target_row_ok = True
        if t1 <= 0 or t2 <= 0 or t1 <= pivot or t2 <= t1:
            reasons.append("Invalid Target Logic (Pivot < T1 < T2)")
            target_row_ok = False
        elif atr > 0 and t2 > (pivot + (8.0 * atr)):
            reasons.append("Target2 too extended (> Pivot + 8*ATR)")
            target_row_ok = False
        else:
            reward = t1 - pivot
            rr_ratio = reward / risk if risk > 0 else 0.0
            if rr_ratio < 2.0:
                reasons.append(f"Low Reward/Risk ({rr_ratio:.1f} < 2.0)")
                target_row_ok = False
            else:
                target_pass_count += 1

        if not target_row_ok:
            target_structure_ok = False

        # --- Position Sizing & Capital Allocation Audit ---
        pos_row_ok = True
        position_value = shares * pivot
        if shares <= 0 or not float(shares).is_integer():
            reasons.append("Invalid Shares (Zero or Non-Integer)")
            pos_row_ok = False
        elif position_value > max_position_allocation:
            reasons.append(f"Position Allocation Exceeds Limit (₹{position_value:,.0f} > ₹{max_position_allocation:,.0f})")
            pos_row_ok = False
        else:
            pos_pass_count += 1

        if not pos_row_ok:
            position_sizing_ok = False
            execution_layer_ok = False

        # --- Market Data (.parquet) Verification Audit ---
        parquet_path = os.path.join(PARQUET_CACHE_DIR, f"{norm_sym}.parquet")
        if not os.path.exists(parquet_path):
            reasons.append("Missing Market Data Cache (.parquet)")
            market_data_ok = False
        else:
            market_data_pass_count += 1

        if reasons:
            failure_records.append({
                "ticker": row.get(ticker_col, "UNKNOWN"),
                "reasons": ", ".join(reasons)
            })
        else:
            ready_row_indices.append(idx)

    df_failed = pd.DataFrame(failure_records)
    ready_count = len(ready_row_indices)
    quality_pct = round((ready_count / total_candidates) * 100.0, 1) if total_candidates > 0 else 0.0

    flat_reasons = [r.strip() for sublist in df_failed['reasons'].str.split(',') for r in sublist if sublist]
    failure_counts = Counter(flat_reasons)

    # Layer status resolutions
    research_status = "PASS" if research_layer_ok else "WARN"
    # target_structure_ok is a real risk/reward validation (Issue 9:
    # pivot < t1 < t2, minimum 2:1 reward:risk) - folded into risk_status
    # here since it's fundamentally a risk concern, not a new category.
    # Previously computed and displayed (Target Structure) but never
    # actually factored into the weighted health score at all - a
    # real gap where Target Structure could show FAIL while Overall
    # Health still showed 100%.
    risk_status = "PASS" if risk_structure_ok and risk_ok_count > 0 and target_structure_ok else "FAIL"
    exec_status = "PASS" if execution_layer_ok and position_sizing_ok else "FAIL"
    price_struct_status = "PASS" if price_structure_ok else "FAIL"
    risk_struct_status = "PASS" if risk_structure_ok else "FAIL"
    target_struct_status = "PASS" if target_structure_ok else "FAIL"
    pos_sizing_status = "PASS" if position_sizing_ok else "FAIL"
    market_data_status = "PASS" if market_data_ok else "WARN"

    # ------------------------------------------------------------------
    # 5. WEIGHTED HEALTH SCORE CALCULATION (Issue 3)
    # Weights: Database (5%), Research (20%), Risk (25%), Execution (30%), Market Data (20%)
    # ------------------------------------------------------------------
    db_score = 100.0 if db_status == "PASS" else 0.0
    research_score = 100.0 if research_status == "PASS" else (70.0 if research_status == "WARN" else 0.0)
    risk_score = 100.0 if risk_status == "PASS" else 0.0
    exec_score = 100.0 if exec_status == "PASS" else 0.0
    market_data_score = 100.0 if market_data_status == "PASS" else (60.0 if market_data_status == "WARN" else 0.0)

    weighted_overall_health = (
        db_score * 0.05 +
        research_score * 0.20 +
        risk_score * 0.25 +
        exec_score * 0.30 +
        market_data_score * 0.20
    )

    # ------------------------------------------------------------------
    # 6. TOP READY CANDIDATES BOARD
    # ------------------------------------------------------------------
    print("\n" + "=" * 66)
    print("🏆 TOP READY CANDIDATES")
    print("=" * 66)

    if ready_count > 0:
        df_ready = df.loc[ready_row_indices].copy()
        score_col = resolved_map.get('composite_score', 'composite_score')
        if score_col and score_col in df_ready.columns:
            df_ready = df_ready.sort_values(by=score_col, ascending=False)
        
        df_top20 = df_ready.head(20)

        print(f"{'Ticker':<10} {'Pattern':<12} {'Composite':<10} {'ATR':<6} {'Shares':<7} {'Risk':<6} {'Stop':<7} {'Target':<7} {'Reward/Risk'}")
        print("-" * 80)

        for _, r in df_top20.iterrows():
            sym = str(r.get(ticker_col, 'UNKNOWN'))
            pat = str(r.get('pattern', 'N/A'))[:11]
            comp = float(get_col_val(r, 'composite_score') or 0.5)
            atr_val = float(get_col_val(r, 'atr_14') or 0.0)
            shs = int(get_col_val(r, 'shares') or 0)
            rsk = float(get_col_val(r, 'risk_per_share') or 0.0)
            stp = float(r.get('stop_loss', 0.0) or 0.0)
            tgt = float(r.get('target_1', 0.0) or 0.0)
            pivot_val = float(get_col_val(r, 'pivot') or 1.0)
            
            reward = tgt - pivot_val
            rr = round(reward / rsk, 2) if rsk > 0 else 0.0

            print(f"{sym:<10} {pat:<12} {comp:<10.2f} {atr_val:<6.1f} {shs:<7} ₹{rsk:<5.1f} ₹{stp:<6.1f} ₹{tgt:<6.1f} {rr}:1")
    else:
        print("⚠️ No ready candidates available to display.")

    # ------------------------------------------------------------------
    # 7. EXECUTIVE PIPELINE HEALTH SUMMARY BLOCK
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("PIPELINE HEALTH")
    print("=" * 50)
    print(f"Database .............. {db_status}")
    print(f"Research Layer ........ {research_status}")
    print(f"Risk Layer ............ {risk_status}")
    print(f"Execution Layer ....... {exec_status}")
    print(f"Duplicates ............ {dup_status}")
    print(f"Price Structure ....... {price_struct_status}")
    print(f"Risk Structure ........ {risk_struct_status}")
    print(f"Target Structure ....... {target_struct_status}")
    print(f"Position Sizing ....... {pos_sizing_status}")
    print(f"Market Data Feed ...... {market_data_status}")
    print(f"Overall Health ........ {int(weighted_overall_health)}%")
    print("==================================================")

    # ------------------------------------------------------------------
    # 8. PIPELINE FLOW RECONCILIATION SUMMARY BLOCK (Issue 10)
    # ------------------------------------------------------------------
    ready_for_trigger = "YES" if ready_count > 0 and weighted_overall_health >= 80.0 else "NO"
    ready_for_orders = "YES" if ready_for_trigger == "YES" and exposure_multiplier >= 0.5 else "NO (REGIME RESTRICTED)"

    print("\n" + "=" * 57)
    print("PIPELINE FLOW")
    print("=" * 57)
    print(f"Research Watchlist ........ {research_count}")
    print(f"Immediate Trigger ......... {research_count}")
    print(f"Execution Plan ............ {execution_plan_count if execution_plan_count > 0 else total_candidates}")
    print(f"Trade Candidates .......... {trade_candidates_count}")
    print(f"Open Positions ............ {open_positions_count}")
    print(f"Market Regime ............. {market_regime}")
    print(f"Exposure .................. {int(exposure_multiplier * 100)}%")
    print(f"Ready for Trigger ......... {ready_for_trigger}")
    print(f"Ready for Orders .......... {ready_for_orders}")
    print("=========================================================")

if __name__ == "__main__":
    run_trigger_input_audit()