import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

known_active = ["HEG", "GLENMARK", "CARRARO", "NAZARA", "UNIPARTS", "GHCLTEXTIL"]

print("=== base_compression for KNOWN active/breakout stocks ===")
for ticker in known_active:
    cur = conn.execute("""
        SELECT score FROM scanner_factors
        WHERE ticker = ? AND factor_name = 'base_compression'
        AND date = (SELECT MAX(date) FROM scanner_factors)
    """, (ticker,))
    row = cur.fetchone()
    print(f"  {ticker}: {row[0] if row else 'NOT FOUND'}")

print()
print("=== overall distribution - how many distinct base_compression values exist today? ===")
cur = conn.execute("""
    SELECT score, COUNT(*) as cnt FROM scanner_factors
    WHERE factor_name = 'base_compression'
    AND date = (SELECT MAX(date) FROM scanner_factors)
    GROUP BY score
    ORDER BY cnt DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  value={row[0]}: {row[1]} stocks share this exact value")

cur2 = conn.execute("""
    SELECT COUNT(DISTINCT score), COUNT(*) FROM scanner_factors
    WHERE factor_name = 'base_compression'
    AND date = (SELECT MAX(date) FROM scanner_factors)
""")
distinct, total = cur2.fetchone()
print(f"\nTotal distinct values: {distinct} out of {total} total rows")

conn.close()
