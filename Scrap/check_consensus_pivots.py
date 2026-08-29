import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("PRAGMA table_info(consensus_pivots)")
print("=== columns ===")
for row in cur.fetchall():
    print(" ", row[1], row[2])
print()
print("=== sample rows ===")
cur2 = conn.execute("SELECT * FROM consensus_pivots LIMIT 5")
cols = [d[0] for d in cur2.description]
print(cols)
for row in cur2.fetchall():
    print(row)
conn.close()
