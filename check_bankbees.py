import pandas as pd

df = pd.read_parquet("parquet_cache/BANKBEES.parquet")
df.columns = [str(c).lower() for c in df.columns]
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print(f"Date range: {df[chr(39)+chr(100)+chr(97)+chr(116)+chr(101)+chr(39)].min()} to {df[chr(39)+chr(100)+chr(97)+chr(116)+chr(101)+chr(39)].max()}")
print(f"Any missing close values: {df[chr(39)+chr(99)+chr(108)+chr(111)+chr(115)+chr(101)+chr(39)].isna().sum()}")
