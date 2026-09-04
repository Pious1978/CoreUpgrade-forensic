import os
cache_dir = "parquet_cache"
files = os.listdir(cache_dir)

candidates = ["NIFTYBANK", "BANKNIFTY", "NSEBANK", "NIFTY_BANK", "NIFTYBEES"]
for c in candidates:
    exists = f"{c}.parquet" in files
    print(f"{c}.parquet exists: {exists}")

print()
print("Any file with BANK or NIFTY in the name:")
matches = [f for f in files if "BANK" in f.upper() or "NIFTY" in f.upper()]
for m in matches[:20]:
    print(f"  {m}")
