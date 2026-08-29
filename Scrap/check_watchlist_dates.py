import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("SELECT Date, COUNT(*) FROM research_watchlist GROUP BY Date ORDER BY Date")
for row in cur.fetchall():
    print(row)
conn.close()
