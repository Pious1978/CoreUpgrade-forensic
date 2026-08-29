import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== how many Tier-1 stocks actually have a real rs_percentile value? ===")
cur = conn.execute("""
    SELECT COUNT(*) FROM research_watchlist
    WHERE Date = (SELECT MAX(Date) FROM research_watchlist)
    AND Tier = 'TIER-1: Core Institutional Leader'
""")
total_tier1 = cur.fetchone()[0]
print(f"Total Tier-1 stocks: {total_tier1}")

print()
print("=== sample of 10 real Tier-1 stocks with their actual rs_percentile ===")
cur2 = conn.execute("""
    SELECT rw.Ticker, ds.rs_percentile
    FROM research_watchlist rw
    LEFT JOIN daily_snapshot ds
        ON REPLACE(UPPER(rw.Ticker), '.NS', '') = REPLACE(UPPER(ds.symbol), '.NS', '')
        AND ds.date = (SELECT MAX(date) FROM daily_snapshot)
    WHERE rw.Date = (SELECT MAX(Date) FROM research_watchlist)
    AND rw.Tier = 'TIER-1: Core Institutional Leader'
    LIMIT 10
""")
for row in cur2.fetchall():
    print(row)

conn.close()
