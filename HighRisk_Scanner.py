"""
HighRisk_Scanner.py

The second sleeve of Alpha1's real dual-sleeve Core/High-Risk
architecture (long_planner_Highrisk.py) - the most architecturally
significant find in the whole Obsolete-folder investigation.
Compounder_Scanner.py is the Core sleeve (quality-gated, stability-
focused); this is the genuinely different High-Risk sleeve
(momentum-chasing, asymmetric-upside, drawdown-penalized).

Deliberately reuses Compounder_Scanner.py's real, tested technical
feature computation and universe loading rather than duplicating it -
the two sleeves differ in SCORING PHILOSOPHY and QUALITY BAR, not in
how price history gets read from our own parquet_cache.

Real, honest differences from the Core sleeve:
- Much more lenient quality bar - this tier explicitly seeks
  speculative, momentum-driven opportunities, not "quality" companies.
  Only rejects companies in genuine financial distress (deeply negative
  margins), not merely mediocre ones.
- Scoring heavily favors momentum and trend, and penalizes drawdown
  more severely (real v9+ formula: momentum*2.5 + returns*1.5 +
  trend*1.5 - drawdown*2.0), rather than the Core sleeve's balance of
  growth, quality, and stability.

Same honest dependency as Compounder_Scanner.py: the (lenient)
fundamentals check still needs a live yfinance .info fetch, so this is
built and logic-tested, but not yet run for real pending Monday's
fundamentals coverage verification.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

from core.config import DB_PATH, BASE_DIR
from core.sector_map import get_sector
from core.excel_utils import save_excel_with_retry

from Compounder_Scanner import (
    load_universe,
    compute_technical_features,
    fetch_fundamentals,
    zscore,
    YFINANCE_AVAILABLE,
)

# Much more lenient than Compounder_Scanner.py's 12% ROE / 150% debt /
# 5% margin gates - this tier explicitly wants speculative, momentum
# names, not quality ones. Only rejects genuine financial distress.
MIN_PROFIT_MARGIN_HIGHRISK = -0.20

MAX_PER_SECTOR = 2
TOP_N_CANDIDATES = 15


def passes_highrisk_gate(fundamentals):
    """
    Deliberately lenient - rejects only genuine financial distress
    (deeply negative margins), not merely mediocre fundamentals. A
    momentum name doesn't need to be a "quality" company to belong in
    this speculative sleeve.
    """

    if not fundamentals:
        return False

    margin = fundamentals.get("profit_margin")

    if margin is None or margin < MIN_PROFIT_MARGIN_HIGHRISK:
        return False

    return True


def calculate_highrisk_score(tech):
    """
    Real v9+ formula from long_planner_Highrisk.py - heavier weight on
    momentum and trend (growth-chasing), drawdown penalized more
    severely than the Core sleeve. Uses raw values here since this
    function scores one stock at a time; z-score normalization across
    the scored universe happens afterward in run(), same as the Core
    sleeve.
    """

    return (
        tech["momentum"] * 2.5 +
        tech["cagr"] * 1.5 +
        tech["trend"] * 1.5 -
        tech["drawdown"] * 2.0
    )


def run():

    print()
    print("=" * 70)
    print("HIGH-RISK SCANNER - MOMENTUM / SPECULATIVE SLEEVE")
    print("=" * 70)

    if not YFINANCE_AVAILABLE:
        print("[-] yfinance not available - cannot fetch fundamentals. Aborting.")
        return

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    print(f"[*] Screening {len(symbols)} stocks for speculative momentum candidates...")
    print("[*] This fetches live fundamentals per stock and may take a while.")

    raw_data = {}

    for symbol in symbols:

        tech = compute_technical_features(symbol)
        if tech is None:
            continue

        fundamentals = fetch_fundamentals(symbol)
        if not passes_highrisk_gate(fundamentals):
            continue

        raw_score = calculate_highrisk_score(tech)
        raw_data[symbol] = {**tech, "raw_score": raw_score}

    if not raw_data:
        print("[+] No stocks cleared both the technical history requirement and the lenient gate.")
        return

    df = pd.DataFrame(raw_data).T

    # Z-score normalize the raw scores against this sleeve's own scored
    # universe - same real discipline as the Core sleeve, rather than
    # trusting an arbitrary raw-value combination directly.
    df["score"] = zscore(df["raw_score"])

    df = df.sort_values("score", ascending=False)

    sector_counts = {}
    selected = []

    for ticker, row in df.iterrows():
        sector = get_sector(ticker)

        sector_warning = None
        if sector != "UNKNOWN" and sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
            sector_warning = f"SECTOR CONCENTRATION - {sector_counts[sector]} other {sector} candidates already selected"

        if sector != "UNKNOWN":
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        selected.append({
            "ticker": ticker,
            "score": round(row["score"], 2),
            "momentum_pct": round(row["momentum"] * 100, 2),
            "cagr_pct": round(row["cagr"] * 100, 2),
            "drawdown_pct": round(row["drawdown"] * 100, 2),
            "volatility_pct": round(row["volatility"] * 100, 2),
            "sector": sector,
            "sector_warning": sector_warning,
        })

        if len(selected) >= TOP_N_CANDIDATES:
            break

    result = pd.DataFrame(selected)

    today = datetime.now().strftime("%Y-%m-%d")
    result["date"] = today

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS highrisk_candidates (
            ticker TEXT,
            score REAL,
            momentum_pct REAL,
            cagr_pct REAL,
            drawdown_pct REAL,
            volatility_pct REAL,
            sector TEXT,
            sector_warning TEXT,
            date TEXT,
            PRIMARY KEY (ticker, date)
        )
    """)

    conn.execute("DELETE FROM highrisk_candidates WHERE date = ?", (today,))
    result.to_sql("highrisk_candidates", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, "HIGHRISK_WATCHLIST.xlsx")
    save_excel_with_retry(result, excel_path, index=False)

    print()
    print(f"[+] {len(result)} high-risk momentum candidates selected")
    print(result[["ticker", "score", "momentum_pct", "cagr_pct", "sector"]].to_string(index=False))
    print(f"[+] Written to highrisk_candidates and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()