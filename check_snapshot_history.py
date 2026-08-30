import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== distinct dates in daily_snapshot ===")
cur = conn.execute("SELECT DISTINCT date FROM daily_snapshot ORDER BY date")
dates = [r[0] for r in cur.fetchall()]
print(f"Total distinct dates: {len(dates)}")
print(dates)

conn.close()
