import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

tables_and_date_cols = [
    ("scanner_factors", "date"),
    ("setup_pivots", "date"),
    ("research_watchlist", "Date"),
    ("consensus_pivots", "date"),
    ("daily_snapshot", "date"),
    ("trade_candidates", "date"),
    ("execution_plan", "created_date"),
]

for table, datecol in tables_and_date_cols:
    try:
        cur = conn.execute(f"SELECT {datecol}, COUNT(*) FROM {table} GROUP BY {datecol} ORDER BY {datecol}")
        rows = cur.fetchall()
        print(f"=== {table} ===")
        for r in rows:
            print(" ", r)
    except Exception as e:
        print(f"=== {table} === ERROR: {e}")
    print()

conn.close()
