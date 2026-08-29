import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

candidates = ["ADANIPOWER", "ADANIENSOL", "SOLARINDS", "CGPOWER", "KOTAKBANK", "ZYDUSLIFE"]

print("=== research_watchlist (ALL readiness/tier levels, not just Immediate Trigger Watch) ===")
for t in candidates:
    cur = conn.execute("SELECT Ticker, Composite_Score, Tier, Readiness, pattern FROM research_watchlist WHERE UPPER(REPLACE(Ticker,'.NS','')) = ?", (t,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {t}: FOUND - {r}")
    else:
        print(f"  {t}: not in research_watchlist at all")

print()
print("=== consensus_pivots ===")
for t in candidates:
    cur = conn.execute("SELECT ticker, pivot_price, pattern, confidence FROM consensus_pivots WHERE UPPER(ticker) = ?", (t,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {t}: FOUND - {r}")
    else:
        print(f"  {t}: no consensus pivot")

conn.close()
