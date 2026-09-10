import sqlite3
from core.config import DB_PATH

conn = sqlite3.connect(DB_PATH)
rows = conn.execute("SELECT id, ticker, status FROM trade_journal WHERE ticker LIKE '% %'").fetchall()
conn.close()

print(f"Tickers with spaces: {len(rows)}")
for row in rows:
    print(row)
