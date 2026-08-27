import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

print("=== ALL rows in consensus_pivots right now (no ticker filter, to see real content) ===")
cur = conn.execute("SELECT ticker, pivot_price, pattern, confidence, date FROM consensus_pivots ORDER BY date DESC LIMIT 30")
for r in cur.fetchall():
    print(" ", r)

print()
print("=== current trade_candidates content for ADANIPOWER / ADANIENSOL, right now ===")
for t in ["ADANIPOWER", "ADANIENSOL"]:
    cur = conn.execute("SELECT ticker, pivot, stop_loss, shares, date FROM trade_candidates WHERE UPPER(ticker) = ?", (t,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {t}: {r}")
    else:
        print(f"  {t}: not in trade_candidates right now")

conn.close()
