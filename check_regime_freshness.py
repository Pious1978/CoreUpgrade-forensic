import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== every row in market_regime, most recent first ===")
cur = conn.execute("SELECT * FROM market_regime ORDER BY date DESC LIMIT 20")
cols = [d[0] for d in cur.description]
print(cols)
for row in cur.fetchall():
    print(row)

print()
print("=== total row count ===")
cur2 = conn.execute("SELECT COUNT(*) FROM market_regime")
print(cur2.fetchone())

conn.close()
