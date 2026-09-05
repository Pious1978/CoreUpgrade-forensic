"""
core/sector_concentration.py

#69 - Real, direct feedback: "five separate bank positions could each
be under 20%, while collectively creating a huge banking-sector bet.
There needs to be a flag somewhere." Existing controls (per-position
20% cap, MAX_PER_SECTOR=3 count) don't directly measure combined
capital percentage in one sector - this does.

Reuses the exact real 35% sector threshold already established in
Portfolio_Optimizer.py, for consistency rather than inventing a new
number for the same underlying concept.
"""

import sqlite3
import pandas as pd

from core.config import DB_PATH
from core.sector_map import get_sector

SECTOR_CONCENTRATION_WARN_PCT = 0.35  # matches Portfolio_Optimizer.py's MAX_WEIGHT_PER_SECTOR


def check_sector_concentration(total_capital):
    """
    Real, live check across actual open positions (trade_journal,
    status != 'CLOSED'). Returns a list of sectors currently exceeding
    the concentration threshold, using each position's real entry
    capital (entry_price x entry_shares) - not a hypothetical or
    backtest number.
    """

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT ticker, entry_price, entry_shares
            FROM trade_journal
            WHERE status != 'CLOSED' AND entry_price IS NOT NULL AND entry_shares IS NOT NULL
        """, conn)
        conn.close()
    except Exception:
        return []

    if df.empty or total_capital <= 0:
        return []

    df["capital_used"] = df["entry_price"] * df["entry_shares"]
    df["sector"] = df["ticker"].apply(get_sector)

    sector_totals = df.groupby("sector")["capital_used"].sum()

    warnings = []

    for sector, total in sector_totals.items():
        if sector == "UNKNOWN":
            continue  # can't meaningfully flag concentration in an unclassified bucket

        pct = total / total_capital

        if pct >= SECTOR_CONCENTRATION_WARN_PCT:
            tickers_in_sector = df[df["sector"] == sector]["ticker"].tolist()
            warnings.append({
                "sector": sector,
                "pct": round(pct * 100, 1),
                "capital": round(total, 2),
                "tickers": tickers_in_sector,
            })

    return warnings