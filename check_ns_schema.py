import pandas as pd

for ticker in ["ABSLAMC", "ADANIENSOL"]:
    print(f"=== {ticker}.parquet ===")
    df1 = pd.read_parquet(f"parquet_cache/{ticker}.parquet")
    print(f"  Rows: {len(df1)}, Columns: {list(df1.columns)}")

    print(f"=== {ticker}.NS.parquet ===")
    df2 = pd.read_parquet(f"parquet_cache/{ticker}.NS.parquet")
    print(f"  Rows: {len(df2)}, Columns: {list(df2.columns)}")
    print()
