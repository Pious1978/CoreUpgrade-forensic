import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("SELECT ticker, pivot, stop_loss, shares FROM trade_candidates ORDER BY shares ASC LIMIT 10")
for row in cur.fetchall():
    print(row)
conn.close()
