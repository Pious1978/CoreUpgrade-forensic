import sys
sys.path.insert(0, "SwingBacktest")
from Historical_Data_Provider import PointInTimeMarketData
from Historical_Scanner_Reconstruction import reconstruct_candidates_at_date
import sqlite3
import datetime

data = PointInTimeMarketData()

target_date = data.trading_dates[-1]
print(f"Reconstructing for the exact most recent date available: {target_date.date()}")

candidates = reconstruct_candidates_at_date(data, target_date)
recon_tickers = set(c["ticker"] for c in candidates)

print(f"Reconstruction count: {len(recon_tickers)}")

conn_live = sqlite3.connect("rs_delivery_history.db")
live_date = conn_live.execute("SELECT MAX(date) FROM setup_pivots").fetchone()[0]
live_tickers = set(row[0] for row in conn_live.execute(
    "SELECT ticker FROM setup_pivots WHERE source IN ('Consolidation', 'Tight_Flag') AND date = ?", (live_date,)
).fetchall())
conn_live.close()

print(f"Live scanner date: {live_date}, count: {len(live_tickers)}")
same_date = target_date.date() == datetime.datetime.strptime(live_date, "%Y-%m-%d").date()
print(f"Exact same date being compared: {same_date}")
print()

overlap = live_tickers & recon_tickers
print(f"Tickers in BOTH: {len(overlap)} out of {len(live_tickers)} live / {len(recon_tickers)} reconstruction")
print(f"Overlap percentage: {len(overlap)/len(live_tickers)*100:.1f}% of live candidates matched")
print()
print("Live-only (missed):", list(live_tickers - recon_tickers)[:15])
print("Reconstruction-only (extra):", list(recon_tickers - live_tickers)[:15])
