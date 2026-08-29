import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("SELECT Tier, COUNT(*) FROM research_watchlist WHERE Date = (SELECT MAX(Date) FROM research_watchlist) GROUP BY Tier")
for row in cur.fetchall():
    print(row)
conn.close()
