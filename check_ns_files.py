import os

cache_dir = "parquet_cache"
files = os.listdir(cache_dir)

test_tickers = ["ABSLAMC", "ADANIENSOL", "ADANIPOWER", "AADHARHFC", "ABB", "3MINDIA"]

for t in test_tickers:
    plain = f"{t}.parquet"
    with_ns = f"{t}.NS.parquet"
    print(f"{t}: plain exists={plain in files}, .NS version exists={with_ns in files}")

print()
print("Total files containing .NS.parquet:", sum(1 for f in files if f.endswith(".NS.parquet")))
print("Sample of .NS.parquet files:", [f for f in files if f.endswith(".NS.parquet")][:10])
