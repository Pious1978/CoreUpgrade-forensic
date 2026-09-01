import sqlite3
import pandas as pd

conn = sqlite3.connect("SwingBacktest/backtest_results.db")
df = pd.read_sql("SELECT date, ticker, source_scanner FROM historical_candidates", conn)
conn.close()

print(f"Total candidate-date-scanner rows: {len(df)}")

grouped = df.groupby(["date", "ticker"])["source_scanner"].nunique()
print(f"Unique (date, ticker) combinations: {len(grouped)}")
print(f"Of those, flagged by 2+ scanners simultaneously: {(grouped >= 2).sum()}")
print(f"Of those, flagged by all 3 scanners simultaneously: {(grouped == 3).sum()}")

overlap_pct = (grouped >= 2).sum() / len(grouped) * 100
print(f"\n{overlap_pct:.1f}% of (date, ticker) combinations are flagged by multiple scanners")
