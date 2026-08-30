import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== Are these genuinely the same date, or two different dates? ===")
cur = conn.execute("""
    SELECT Ticker, Date, Tier, Composite_Score
    FROM research_watchlist
    WHERE Ticker IN ('GRSE', 'JSWDULUX', 'FORTIS')
    ORDER BY Ticker, Date DESC
""")
for row in cur.fetchall():
    print(row)

print()
print("=== Distinct dates present in research_watchlist ===")
cur2 = conn.execute("SELECT DISTINCT Date FROM research_watchlist ORDER BY Date DESC")
for row in cur2.fetchall():
    print(row)

conn.close()
