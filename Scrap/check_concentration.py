import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("SELECT ticker, pivot, shares, (shares*pivot) as capital_used FROM trade_candidates ORDER BY capital_used DESC LIMIT 10")
for row in cur.fetchall():
    print(row)
conn.close()
