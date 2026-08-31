import pandas as pd
import numpy as np
import os

PARQUET_CACHE_DIR = "parquet_cache"
ticker = "AQYLON"

path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")
df = pd.read_parquet(path)
df.columns = [str(c).lower() for c in df.columns]
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date").sort_index()
df = df.dropna(subset=["close", "high", "low"])

print(f"=== {ticker} raw data overview ===")
print(f"Total rows: {len(df)}")
print(f"Date range: {df.index[0].date()} to {df.index[-1].date()}")
print()

close = df["close"]

print("First 5 closes:")
print(close.head())
print()
print("Last 5 closes:")
print(close.tail())
print()

pct_changes = close.pct_change()
biggest_single_day_moves = pct_changes.abs().sort_values(ascending=False).head(10)
print("=== 10 biggest single-day % moves (possible split/data errors) ===")
for date, pct in biggest_single_day_moves.items():
    idx = close.index.get_loc(date)
    prev_price = close.iloc[idx-1] if idx > 0 else None
    curr_price = close.iloc[idx]
    print(f"{date.date()}: {pct*100:+.1f}%  (prev={prev_price:.2f} -> curr={curr_price:.2f})")

print()
cagr_years = len(close) / 252
cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / cagr_years) - 1 if cagr_years > 0 else 0
momentum = close.pct_change(63).iloc[-1] if len(close) > 63 else 0
volatility = close.pct_change().std() * np.sqrt(252)
drawdown = (close / close.cummax() - 1).min()
ma200 = close.rolling(200).mean().iloc[-1]
trend = 1 if close.iloc[-1] > ma200 else 0

print("=== Computed technical features ===")
print(f"CAGR: {cagr*100:.2f}%")
print(f"63-day momentum: {momentum*100:.2f}%")
print(f"Volatility (annualized): {volatility*100:.2f}%")
print(f"Max drawdown: {drawdown*100:.2f}%")
print(f"Trend (above 200MA): {trend}")
print(f"First close: {close.iloc[0]:.2f}, Last close: {close.iloc[-1]:.2f}")