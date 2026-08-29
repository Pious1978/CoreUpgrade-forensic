import pandas as pd

yahoo = pd.read_parquet("parquet_cache_archive_yahoo/BHARTIARTL.NS.parquet")
bhav = pd.read_parquet("parquet_cache/BHARTIARTL.parquet")

yahoo = yahoo.reset_index()
yahoo.columns = [c.lower() for c in yahoo.columns]
yahoo["date"] = pd.to_datetime(yahoo["date"])
bhav["date"] = pd.to_datetime(bhav["date"])

merged = pd.merge(
    bhav[["date", "close"]].rename(columns={"close": "bhav_close"}),
    yahoo[["date", "close"]].rename(columns={"close": "yahoo_close"}),
    on="date", how="inner"
)
merged["pct_diff"] = round(((merged["bhav_close"] - merged["yahoo_close"]) / merged["yahoo_close"]) * 100, 3)
print(merged.to_string(index=False))
