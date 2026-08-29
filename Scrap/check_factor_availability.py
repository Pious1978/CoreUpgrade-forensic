import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== does scanner_factors exist and what factor_names are stored? ===")
try:
    cur = conn.execute("SELECT DISTINCT factor_name FROM scanner_factors")
    names = [r[0] for r in cur.fetchall()]
    print(f"Found {len(names)} distinct factor names:")
    for n in names:
        print(f"  {n}")
except Exception as e:
    print(f"Error: {e}")

print()
print("=== sample real values for one recent ticker, most recent date ===")
try:
    cur = conn.execute("""
        SELECT ticker, factor_name, score, date
        FROM scanner_factors
        WHERE date = (SELECT MAX(date) FROM scanner_factors)
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")

conn.close()
