import sqlite3

conn_live = sqlite3.connect("rs_delivery_history.db")
live_count = conn_live.execute(
    "SELECT COUNT(*) FROM setup_pivots WHERE source IN ('Consolidation', 'Tight_Flag') AND date = (SELECT MAX(date) FROM setup_pivots)"
).fetchone()[0]
live_date = conn_live.execute("SELECT MAX(date) FROM setup_pivots").fetchone()[0]
live_tickers = set(row[0] for row in conn_live.execute(
    "SELECT ticker FROM setup_pivots WHERE source IN (Consolidation, Tight_Flag) AND date = ?".replace("Consolidation", "'Consolidation'").replace("Tight_Flag", "'Tight_Flag'"), (live_date,)
).fetchall())
conn_live.close()

conn_bt = sqlite3.connect("SwingBacktest/backtest_results.db")
recon_date = conn_bt.execute("SELECT MAX(date) FROM historical_candidates").fetchone()[0]
recon_count = conn_bt.execute("SELECT COUNT(*) FROM historical_candidates WHERE date = ?", (recon_date,)).fetchone()[0]
recon_tickers = set(row[0] for row in conn_bt.execute(
    "SELECT ticker FROM historical_candidates WHERE date = ?", (recon_date,)
).fetchall())
conn_bt.close()

print(f"=== LIVE scanner - date: {live_date}, count: {live_count} ===")
print(f"=== RECONSTRUCTION - most recent date: {recon_date}, count: {recon_count} ===")
print()

overlap = live_tickers & recon_tickers
print(f"Tickers in BOTH: {len(overlap)}")
print(f"Tickers ONLY in live (recon missed): {len(live_tickers - recon_tickers)}")
print(f"Tickers ONLY in reconstruction (extra): {len(recon_tickers - live_tickers)}")
print()
print("Sample of tickers only in LIVE (first 10):", list(live_tickers - recon_tickers)[:10])
print("Sample of tickers only in RECONSTRUCTION (first 10):", list(recon_tickers - live_tickers)[:10])
