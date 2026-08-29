import pandas as pd
df = pd.read_parquet("parquet_cache_archive_yahoo/RELIANCE.NS.parquet")
print("Columns:", list(df.columns))
print("Date range:", df.index.min() if df.index.name else df.iloc[0], "to", df.index.max() if df.index.name else df.iloc[-1])
print(df.tail(3))
