"""
Bootstrap_History.py
---------------------------------------------------------
Run this ONCE to historical data backfill into rs_delivery_history.db
"""
import os
import pandas as pd
import sqlite3
from RS_Accel_Delivery_Trend import init_db, ingest_bhavcopy_to_pipeline

BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest"
DB_PATH = os.path.join(BASE_DIR, "rs_delivery_history.db")

def bootstrap_from_historical_csvs():
    conn = init_db(DB_PATH)
    
    # 💡 REPLACE THIS PATH: Point this to wherever you archive your daily NSE Bhavcopies or historical dumps
    historical_data_dir = r"C:\Users\GS102\OneDrive\Research\Invest\HistoricalBhavcopies" 
    
    if not os.path.exists(historical_data_dir):
        print(f"[-] Created placeholder directory at {historical_data_dir}")
        print("    Please drop your historical daily CSVs there and re-run.")
        os.makedirs(historical_data_dir, exist_ok=True)
        return

    # Loop through sorted daily files (e.g., bhav_20260101.csv, bhav_20260102.csv)
    files = sorted([f for f in os.listdir(historical_data_dir) if f.endswith('.csv')])
    
    print(f"[*] Found {len(files)} historical data files to process...")
    
    for file in files:
        file_path = os.path.join(historical_data_dir, file)
        
        # Parse the date out of your file name convention (Example assumes: YYYY-MM-DD or similar)
        # Adapt this parsing string to exactly match your filename layout!
        try:
            # Assumes file name structure like: "bhav_2026-05-12.csv"
            date_str = file.replace("bhav_", "").replace(".csv", "")
            
            df = pd.read_csv(file_path)
            
            # Mock or pull your historical RS scores for that day.
            # If you don't have historical daily RS saved, the engine will default them to 50.0
            dummy_rs_dict = {} 
            
            print(f"[*] Ingesting {file} for date {date_str}...")
            ingest_bhavcopy_to_pipeline(conn, df, date_str, dummy_rs_dict)
            
        except Exception as e:
            print(f"[-] Skipped file {file} due to error: {e}")

    conn.close()
    print("[+] Bootstrap complete. Try re-running RS_Accel_Delivery_Trend.py now.")

if __name__ == "__main__":
    bootstrap_from_historical_csvs()