import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("SELECT ticker, composite_score, tier FROM trade_candidates ORDER BY composite_score DESC")
for row in cur.fetchall():
    print(row)
conn.close()
