import sqlite3
for db in ["market_data.db", "rs_delivery_history.db"]:
    print(f"=== {db} ===")
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for row in cur.fetchall():
        print(" -", row[0])
    conn.close()
