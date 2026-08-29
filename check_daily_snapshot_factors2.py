import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

known_active = ["HEG", "GLENMARK", "CARRARO", "NAZARA", "UNIPARTS", "GHCLTEXTIL"]

print("=== rs_percentile, rs_acceleration, delivery_score for known-active stocks ===")
for ticker in known_active:
    cur2 = conn.execute("""
        SELECT rs_percentile, rs_acceleration, delivery_score FROM daily_snapshot
        WHERE symbol = ?
        AND date = (SELECT MAX(date) FROM daily_snapshot)
    """, (ticker,))
    row = cur2.fetchone()
    print(f"  {ticker}: {row if row else 'NOT FOUND'}")

print()
print("=== overall distribution health ===")
cur3 = conn.execute("""
    SELECT COUNT(DISTINCT rs_percentile), COUNT(*) FROM daily_snapshot
    WHERE date = (SELECT MAX(date) FROM daily_snapshot)
""")
print(f"rs_percentile: {cur3.fetchone()}")

conn.close()
