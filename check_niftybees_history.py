import pandas as pd
import os

path = "parquet_cache/NIFTYBEES.parquet"
if os.path.exists(path):
    df = pd.read_parquet(path)
    df.columns = [str(c).lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    print(f"NIFTYBEES real history: {len(df)} rows, {df['date'].min()} to {df['date'].max()}")
else:
    print("NIFTYBEES.parquet not found in parquet_cache")

print()
yahoo_path = "parquet_cache_archive_yahoo/NIFTYBEES.NS.parquet"
print(f"Yahoo archive file exists for NIFTYBEES: {os.path.exists(yahoo_path)}")
