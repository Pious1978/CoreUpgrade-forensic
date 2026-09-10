import sqlite3
from core.config import DB_PATH

conn = sqlite3.connect(DB_PATH)

fixes = {
    "BHARAT ELECTRONICS LTD": "BEL",
    "JIO FIN SERVICES LTD": "JIOFIN",
    "LARSEN & TOUBRO LTD.": "LT",
    "RELIANCE INDUSTRIES LTD": "RELIANCE",
}

for bad, good in fixes.items():
    cursor = conn.execute("UPDATE trade_journal SET ticker = ? WHERE ticker = ?", (good, bad))
    print(f"{bad} -> {good}: {cursor.rowcount} row(s) updated")

conn.commit()
conn.close()
