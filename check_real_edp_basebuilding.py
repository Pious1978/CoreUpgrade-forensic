import sqlite3
import sys
sys.path.insert(0, ".")
from core.technical_indicators import compute_atr
import math

def calculate_edp(distance_pct, atr_pct):
    if atr_pct is None or atr_pct <= 0:
        return None
    expected_days = abs(distance_pct) / (atr_pct + 1e-8)
    if expected_days <= 1.2:
        return "1 Trading Day"
    elif expected_days <= 3.0:
        return f"{math.ceil(expected_days)} Trading Days"
    else:
        return f"{math.ceil(expected_days)}-{math.ceil(expected_days*1.5)} Days"

conn = sqlite3.connect("rs_delivery_history.db")
cur = conn.execute("""
    SELECT ticker, pivot, execution_state, last_price
    FROM trade_candidates
    WHERE execution_state = 'BASE_BUILDING'
    LIMIT 8
""")

for row in cur.fetchall():
    ticker, pivot, state, price = row
    if not price or not pivot:
        continue
    distance = round(((price - pivot) / pivot) * 100, 2)
    _, atr_pct = compute_atr(ticker)
    edp = calculate_edp(distance, atr_pct)
    print(f"{ticker}: distance={distance}%, atr_pct={atr_pct}%, EDP={edp}")

conn.close()
