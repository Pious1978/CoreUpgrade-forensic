import pandas as pd
yahoo = pd.read_parquet("parquet_cache_archive_yahoo/RELIANCE.NS.parquet")
bhav = pd.read_parquet("parquet_cache/RELIANCE.parquet")
print("=== Yahoo tail ===")
print(yahoo.tail(5))
print()
print("=== Bhav head ===")
print(bhav.head(5))
