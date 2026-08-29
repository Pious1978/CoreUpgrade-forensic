import sqlite3
for db in ["market_data.db", "rs_delivery_history.db"]:
    print(f"=== {db} ===")
    conn = sqlite3.connect(db)
    for table in ["daily_snapshot", "scanner_factors"]:
        print(f"--- {table} ---")
        cur = conn.execute(f"PRAGMA table_info({table})")
        for row in cur.fetchall():
            print(" ", row[1], row[2])
        cur2 = conn.execute(f"SELECT COUNT(*) FROM {table}")
        print("  row count:", cur2.fetchone()[0])
    conn.close()
