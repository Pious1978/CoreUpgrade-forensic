import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

cleanup = [
    ("scanner_factors", "date"),
    ("setup_pivots", "date"),
    ("research_watchlist", "Date"),
    ("consensus_pivots", "date"),
    ("daily_snapshot", "date"),
]

for table, datecol in cleanup:
    cur = conn.execute(f"SELECT MAX({datecol}) FROM {table}")
    latest = cur.fetchone()[0]
    cur2 = conn.execute(f"DELETE FROM {table} WHERE {datecol} != ?", (latest,))
    print(f"{table}: deleted {cur2.rowcount} stale rows, kept latest date {latest}")

conn.commit()
conn.execute("VACUUM")
conn.close()
print("Done - database compacted.")
