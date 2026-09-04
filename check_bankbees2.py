import pandas as pd

df = pd.read_parquet("parquet_cache/BANKBEES.parquet")
df.columns = [str(c).lower() for c in df.columns]
print("Rows:", len(df))
print("Columns:", list(df.columns))
print("First date:", df["date"].min())
print("Last date:", df["date"].max())
print("Missing close:", df["close"].isna().sum())

nifty = pd.read_parquet("parquet_cache/NIFTYBEES.parquet")
nifty.columns = [str(c).lower() for c in nifty.columns]
print()
print("For comparison, NIFTYBEES rows:", len(nifty))
