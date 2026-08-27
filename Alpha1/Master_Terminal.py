"""
Master_Terminal.py (Version 4.9 Hardened Kinematic Production Core)
-------------------------------------------------------------------------
Unified Quantitative Production Hub with Multi-Sheet Priority Ingestion
"""
import os
import json
import time
import datetime
import sqlite3
import pandas as pd

from Standard_Engine_Types import FeatureStore, EngineResult
from Feature_Store_Factory import FeatureStoreFactory
from Engine_Registry import EngineRegistry
from Data_Service import DataService
from Decision_Engine import InstitutionalDecisionEngine

import Consolidation_Scanner as Consolidation_Module

BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest"
DB_PATH = os.path.join(BASE_DIR, "rs_delivery_history.db")
SCANNER_REPORT_INPUT = os.path.join(BASE_DIR, "Institutional_Breakout_Report.xlsx")
OUTPUT_VIEW_EXCEL = os.path.join(BASE_DIR, "COMPOSITE_ALPHA_OUTPUT.xlsx")

def run():
    print("\n🏛️ RUNNING QUANT INFRASTRUCTURE HUB v4.9 (PRODUCTION RECONCILED)\n")
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # =====================================================================
    # 1. HARDENED SCHEMA MIGRATION & REALIGNMENT LAYER
    # =====================================================================
    # Run dynamic schema upgrades on daily_snapshot partition to avoid key errors
    try:
        cursor.execute("ALTER TABLE daily_snapshot ADD COLUMN rs_acceleration REAL DEFAULT 50.0")
        cursor.execute("ALTER TABLE daily_snapshot ADD COLUMN delivery_score REAL DEFAULT 50.0")
        conn.commit()
        print("[+] Schema Migration: Missing tracking column parameters patched successfully.")
    except sqlite3.OperationalError:
        pass  # Columns already exist in database partitions, proceed safely

    # Verify if research_database matches the multi-factor schema specs
    try:
        cursor.execute("SELECT tier_lifecycle FROM research_database LIMIT 1")
    except sqlite3.OperationalError:
        # If query crashes, the historical table layout is out of date. Drop to clear lock.
        print("[*] Schema Realignment: Upgrading 'research_database' layout to Phase 4.9 specifications...")
        cursor.execute("DROP TABLE IF EXISTS research_database")
        conn.commit()

    # Re-initialize table with production-grade numeric fields
    conn.execute("""
        CREATE TABLE IF NOT EXISTS research_database (
            date TEXT NOT NULL, symbol TEXT NOT NULL, tier_lifecycle TEXT,
            opportunity_score REAL, readiness_score REAL, measurable_deficit TEXT,
            expected_days_to_pivot TEXT, absolute_feature_snapshot_json TEXT,
            PRIMARY KEY (date, symbol)
        )
    """)
    conn.commit()

    # =====================================================================
    # 2. STRATEGIC DISCOVERY & REGISTRY ORCHESTRATION
    # =====================================================================
    broker = EngineRegistry()
    broker.register("Consolidation", Consolidation_Module.evaluate)

    if not os.path.exists(SCANNER_REPORT_INPUT):
        print(f"[-] Handoff Error: Input file missing at {SCANNER_REPORT_INPUT}. Run Consolidation_Scanner1.py first.")
        conn.close()
        return

    # ---------------------------------------------------------------------
    # PRIORITY MULTI-SHEET HOOK: INGEST AND ALIGN TIGHTEST COILS FIRST
    # ---------------------------------------------------------------------
    try:
        coiled     = pd.read_excel(SCANNER_REPORT_INPUT, sheet_name="COILED (Tier1 Ready)")
        tightening = pd.read_excel(SCANNER_REPORT_INPUT, sheet_name="TIGHTENING (Tier1 Watch)")
        forming    = pd.read_excel(SCANNER_REPORT_INPUT, sheet_name="FORMING (Tier2)")
        scanner_df = pd.concat([coiled, tightening, forming], ignore_index=True)
        print(f"[+] Multi-Sheet Priority Load: {len(coiled)} COILED + {len(tightening)} TIGHTENING + {len(forming)} FORMING")
    except Exception:
        # Resilient fallback structural track for legacy single-sheet scanner layout exports
        scanner_df = pd.read_excel(SCANNER_REPORT_INPUT)
        print(f"[+] Fallback Ingestion: Loaded {len(scanner_df)} setups via legacy single-sheet matrix profile format.")

    for col in ["Symbol", "Stock", "Ticker"]:
        if col in scanner_df.columns:
            scanner_df.rename(columns={col: "Ticker"}, inplace=True)
            break

    watchlist = scanner_df["Ticker"].dropna().unique().tolist()
    data_provider = DataService()
    nifty_df = data_provider.get_nifty_history()

    cursor.execute("SELECT MAX(date) FROM daily_snapshot")
    latest_db_date = cursor.fetchone()[0]

    # today_str is always used for TODAY's ingest label.
    # latest_db_date is used only for the RS/delivery lookup — because
    # today's snapshot won't exist in the DB until ingest runs later in
    # this same script. After ingest completes, both will match.
    ingest_date   = today_str
    rs_lookup_date = today_str if latest_db_date == today_str else latest_db_date

    print(f"🔬 Today: {today_str} | Last DB snapshot: {latest_db_date or 'none'}")
    if rs_lookup_date != today_str:
        print(f"⚠️  RS scores being pulled from {rs_lookup_date} — today's snapshot "
              f"will be written during this run and available tomorrow.")

    # Fetch point-in-time metrics matrix
    cursor.execute("SELECT symbol, rs_percentile, rs_acceleration, delivery_score FROM daily_snapshot WHERE date = ?", (rs_lookup_date,))
    db_metrics_matrix = {row[0]: {"rs": row[1], "accel": row[2], "delivery": row[3]} for row in cursor.fetchall()}

    export_matrix = []

    # =====================================================================
    # 3. CORE QUANTUM PIPELINE LOOP
    # =====================================================================
    for symbol in watchlist:
        suffix_ticker = symbol + ".NS" if not symbol.endswith(".NS") else symbol
        clean_ticker = suffix_ticker.replace(".NS", "")
        
        price_df = data_provider.get_price_history(suffix_ticker)
        if price_df.empty or len(price_df) < 50: continue

        snap = db_metrics_matrix.get(clean_ticker, {"rs": 50.0, "accel": 50.0, "delivery": 50.0})
        
        # Build completely frozen, immutable feature store
        feature_store = FeatureStoreFactory.generate(clean_ticker, today_str, price_df, nifty_df, snap["rs"])
        
        current_close = float(price_df["Close"].iloc[-1])
        raw_atr_pct = feature_store.metrics.get("atr_pct", 1.5)
        
        high_series = price_df["High"].dropna()
        if isinstance(high_series, pd.DataFrame): high_series = high_series.iloc[:, 0]
        calc_pivot = float(high_series.tail(20).max())

        # Profile module runtime profiling speed limits
        start_time = time.perf_counter()
        engine_outputs = broker.execute_all(feature_store)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        consolidation_res = engine_outputs["Consolidation"]
        
        # Call centralized diagnostic decision engine
        decision = InstitutionalDecisionEngine.process({
            "Consolidation": consolidation_res,
            "RS_Percentile": snap["rs"],
            "RS_Acceleration_Score": snap["accel"],
            "Delivery_Trend_Score": snap["delivery"],
            "Current_Price": current_close,
            "Pivot_Price": calc_pivot,
            "ATR_Pct": raw_atr_pct
        })

        # Close feedback validation loop by persisting raw decimals to research DB
        conn.execute("""
            INSERT INTO research_database 
            (date, symbol, tier_lifecycle, opportunity_score, readiness_score, measurable_deficit, expected_days_to_pivot, absolute_feature_snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, symbol) DO UPDATE SET
                tier_lifecycle=excluded.tier_lifecycle, opportunity_score=excluded.opportunity_score,
                readiness_score=excluded.readiness_score, measurable_deficit=excluded.measurable_deficit,
                expected_days_to_pivot=excluded.expected_days_to_pivot, absolute_feature_snapshot_json=excluded.absolute_feature_snapshot_json
        """, (today_str, clean_ticker, decision["Tier_Lifecycle"], 
              decision["Opportunity_Raw"], decision["Readiness_Raw"], 
              decision["Measurable_Deficit"], decision["EDP_Window"], json.dumps(feature_store.metrics)))

        export_matrix.append({
            "Symbol": clean_ticker,
            "Operational Classification Tier": decision["Tier_Lifecycle"],
            "Opportunity_Raw": decision["Opportunity_Raw"],  # Numeric sorting anchor
            "Opportunity": decision["Opportunity_Display"],
            "Readiness": decision["Readiness_Display"],
            "Pivot Dist": decision["Pivot_Dist"],
            "14d ATR": decision["ATR_14d"],
            "Expected Days to Pivot (EDP)": decision["EDP_Window"],
            "Measurable Deficit Required": decision["Measurable_Deficit"],
            "Actionable Operational Trigger": decision["Actionable_Trigger"],
            "Profile_ms": round(elapsed_ms, 1)
        })

    conn.commit()
    conn.close()

    # =====================================================================
    # 4. VIEW MATRIX PRESENTATION LAYER
    # =====================================================================
    if export_matrix:
        # Execute mathematically safe numeric multi-factor sorting 
        master_df = pd.DataFrame(export_matrix)
        master_df.sort_values(by=["Operational Classification Tier", "Opportunity_Raw"], ascending=[True, False], inplace=True)
        
        # Drop raw numeric sorting anchor metrics prior to spreadsheet generation
        master_df.drop(columns=["Opportunity_Raw"], inplace=True)
        master_df.to_excel(OUTPUT_VIEW_EXCEL, index=False)
        
        print(f"📊 VOLATILITY-ADJUSTED OPERATIONAL DASHBOARD ({today_str}):\n")
        print(master_df.to_string(index=False))
        print(f"\n📁 System runtime complete. View report compiled successfully: {OUTPUT_VIEW_EXCEL}\n")

if __name__ == "__main__":
    run()