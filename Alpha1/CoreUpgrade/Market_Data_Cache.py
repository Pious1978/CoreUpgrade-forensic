import os
import json
import time
import datetime
import pandas as pd
import yfinance as yf
import warnings

# Import configurations from your central registry
from core.config import PARQUET_CACHE_DIR, UNIVERSE_CSV_PATH, CACHE_HISTORY_PERIOD

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURATION
# =============================================================================
MANIFEST_FILE = os.path.join(PARQUET_CACHE_DIR, "manifest.json")
BATCH_SIZE = 50
CURRENT_SCHEMA_VERSION = "v1.0"

os.makedirs(PARQUET_CACHE_DIR, exist_ok=True)

class MarketDataEngine:
    def __init__(self):
        self.manifest = self._load_manifest()
        self.today_str = datetime.date.today().isoformat()
        
    def _load_manifest(self) -> dict:
        if os.path.exists(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
                
        # Initialize a fresh manifest structure
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "last_full_run": None,
            "verified_count": 0,
            "symbols": {}
        }

    def _save_manifest(self):
        with open(MANIFEST_FILE, "w") as f:
            json.dump(self.manifest, f, indent=4)

    def _get_universe(self) -> list:
        if not os.path.exists(UNIVERSE_CSV_PATH):
            return []
        try:
            df = pd.read_csv(UNIVERSE_CSV_PATH)
            df.columns = [c.strip().upper() for c in df.columns]
            if "SERIES" in df.columns:
                df = df[df["SERIES"] == "EQ"]
            symbols = df["SYMBOL"].dropna().astype(str).str.strip().str.upper().unique().tolist()
            return [s + ".NS" if not s.endswith(".NS") else s for s in symbols]
        except Exception:
            return []

    def verify_cache(self, universe: list) -> int:
        verified_count = 0
        for sym in universe:
            file_path = os.path.join(PARQUET_CACHE_DIR, f"{sym}.parquet")
            if os.path.exists(file_path):
                try:
                    df = pd.read_parquet(file_path)
                    if not df.empty and len(df) > 5:
                        verified_count += 1
                except Exception:
                    pass
        return verified_count

    def update_cache(self):
        print("======================================================================")
        print("🗄️ MARKET DATA CACHE ENGINE (Incremental Batch Mode)")
        print("======================================================================\n")

        universe = self._get_universe()
        if not universe:
            print(f"❌ No universe loaded from {UNIVERSE_CSV_PATH}. Exiting.")
            return

        stale_symbols = []
        for sym in universe:
            sym_meta = self.manifest["symbols"].get(sym, {})
            if sym_meta.get("last_updated") != self.today_str:
                stale_symbols.append(sym)

        print(f"[*] Universe Size : {len(universe)}")
        print(f"[*] Up to Date    : {len(universe) - len(stale_symbols)}")
        print(f"[*] Stale/Missing : {len(stale_symbols)}")

        if not stale_symbols:
            print("\n✅ Cache is fully up to date for today's session.")
            return

        print("\n[*] Initiating batched download for stale symbols...\n")
        total_stale = len(stale_symbols)
        
        for i in range(0, total_stale, BATCH_SIZE):
            batch = stale_symbols[i : i + BATCH_SIZE]
            
            try:
                data = yf.download(
                    batch, 
                    period=CACHE_HISTORY_PERIOD, 
                    threads=True, 
                    progress=False, 
                    auto_adjust=True
                )
            except Exception as e:
                print(f"[⚠️] Batch download failed: {e}")
                continue

            if data.empty:
                continue

            for sym in batch:
                try:
                    if len(batch) > 1:
                        if isinstance(data.columns, pd.MultiIndex):
                            if sym not in data.columns.get_level_values(0) and sym not in data.columns.get_level_values(-1):
                                continue
                            if sym in data.columns.get_level_values(0):
                                df = data[sym].dropna()
                            else:
                                df = data.xs(sym, axis=1, level=-1).dropna()
                        else:
                            df = data.dropna()
                    else:
                        df = data.dropna()

                    if df.empty or len(df) < 20:
                        self.manifest["symbols"][sym] = {
                            "status": "failed",
                            "reason": "insufficient_data",
                            "last_updated": self.today_str
                        }
                        continue

                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    file_path = os.path.join(PARQUET_CACHE_DIR, f"{sym}.parquet")
                    df.to_parquet(file_path, engine="pyarrow")

                    self.manifest["symbols"][sym] = {
                        "status": "success",
                        "last_updated": self.today_str,
                        "row_count": len(df),
                        "last_close_date": str(df.index[-1].date())
                    }
                    
                except Exception as inner_e:
                    self.manifest["symbols"][sym] = {
                        "status": "failed",
                        "reason": str(inner_e),
                        "last_updated": self.today_str
                    }

            print(f" -> Processed Batch [{min(i + BATCH_SIZE, total_stale)} / {total_stale}]")
            self._save_manifest()
            time.sleep(1.5)

        print("\n[*] Verifying cache integrity...")
        verified = self.verify_cache(universe)
        
        self.manifest["last_full_run"] = self.today_str
        self.manifest["verified_count"] = verified
        self._save_manifest()
        
        print(f"✅ Cache update complete. Usable Parquets: {verified} / {len(universe)}")
        print("======================================================================\n")

if __name__ == "__main__":
    engine = MarketDataEngine()
    engine.update_cache()
