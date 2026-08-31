import sqlite3

conn = sqlite3.connect("SwingBacktest/backtest_results.db")

print("=== Actual current schema of backtest_trades ===")
cur = conn.execute("PRAGMA table_info(backtest_trades)")
for row in cur.fetchall():
    print(row)

print()
print("=== Sample of actual stored values ===")
cur2 = conn.execute("SELECT ticker, stop, target_1, target_2, exit_reason FROM backtest_trades LIMIT 5")
for row in cur2.fetchall():
    print(row)

conn.close()
