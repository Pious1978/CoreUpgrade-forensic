import os
import json
import pandas as pd
from core.config import PARQUET_CACHE_DIR

# =============================================================================
# CONFIGURATION
# =============================================================================
MANIFEST_FILE = os.path.join(PARQUET_CACHE_DIR, "manifest.json")
TARGET_SCHEMA_VERSION = "v1.1"

def calculate_atr(df: pd.DataFrame, period=14) -> pd.DataFrame:
    """Example Migration: Appending a 14-day ATR column locally."""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR_14'] = true_range.rolling(window=period).mean()
    return df

def run_schema_migration():
    print("======================================================================")
    print("🔄 LOCAL SCHEMA MIGRATION ENGINE")
    print("======================================================================\n")

    if not os.path.exists(MANIFEST_FILE):
        print("⚠️ Manifest not found. Run Market_Data_Cache.py first.")
        return

    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)

    current_version = manifest.get("schema_version", "v1.0")
    if current_version == TARGET_SCHEMA_VERSION:
        print(f"✅ Schema is already at {TARGET_SCHEMA_VERSION}. No migration needed.")
        return

    print(f"[*] Upgrading schema: {current_version} -> {TARGET_SCHEMA_VERSION}")
    
    migrated_count = 0
    symbols = list(manifest.get("symbols", {}).keys())

    for sym in symbols:
        file_path = os.path.join(PARQUET_CACHE_DIR, f"{sym}.parquet")
        if not os.path.exists(file_path):
            continue

        try:
            df = pd.read_parquet(file_path)
            
            # Note: Ensure columns are properly cased for your logic. 
            # Cup_and_Handle.py expects lowercase ['high', 'low', 'close'] 
            if 'High' in df.columns:
                df = calculate_atr(df)
                df.to_parquet(file_path, engine="pyarrow")
                migrated_count += 1
            
        except Exception as e:
            print(f"[⚠️] Migration failed for {sym}: {e}")

    manifest["schema_version"] = TARGET_SCHEMA_VERSION
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=4)

    print(f"\n✅ Migration complete. {migrated_count} parquets upgraded to {TARGET_SCHEMA_VERSION}.")

if __name__ == "__main__":
    run_schema_migration()
