import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("""
    SELECT Ticker, Tier FROM research_watchlist
    WHERE Date = (SELECT MAX(Date) FROM research_watchlist)
    AND Ticker IN ('JSWDULUX', 'FORTIS', 'DOMS', 'JINDRILL')
""")
for row in cur.fetchall():
    print(row)
conn.close()
