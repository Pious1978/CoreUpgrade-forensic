"""
Sector_Strength_Ranker.py

Real, new capability - a genuine sector-strength ranking, not just the
existing concentration cap. Risk_Positioning_Engine.py's sector cap
answers "how many stocks from one sector am I allowed to hold" -
this answers a completely different question: "which sectors are
genuinely strong right now."

Liquidity-weighted aggregate scoring, adapted from a real, working idea
in Alpha1's hybrid_alpha_scanner1.py: a sector's score is the
liquidity-weighted average of its constituent stocks' relative
strength, using log1p(turnover) as the weight rather than raw turnover.
Log-dampening matters here - without it, a single mega-liquid stock
(e.g. a large-cap bank) could completely dominate its sector's score,
drowning out what every other stock in that sector is actually doing.

Uses our own real, backfilled parquet_cache and the same real RS
formula RelativeStrengthEngine.py computes live (250-day return minus
the NIFTY benchmark's own 250-day return) - fully price-based, no live
fundamentals fetch needed, no Monday dependency.

HONEST LIMITATION: core/sector_map.py currently covers 212 of roughly
2,500+ universe stocks (a known, structural ceiling - sectoral indices
only include NSE's largest, most liquid names). This ranking is only
as complete as that coverage; a sector with few mapped stocks will
have a less statistically reliable score than one with many.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, UNIVERSE_CSV_PATH, NIFTY_BENCHMARK_SYMBOL, MIN_TRADING_DAYS_RS
from core.sector_map import get_sector, UNIVERSE as SECTOR_UNIVERSE

MIN_STOCKS_PER_SECTOR = 2  # below this, a sector's score isn't statistically meaningful


def load_universe():
    """Reuses the same NSE_EQ.csv universe file every other scanner in
    this pipeline already relies on, for consistency."""

    try:
        df = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            return []

        symbol_col = df.columns[cols.index("SYMBOL")]
        symbols = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()

        return sorted(set(s for s in symbols if len(s) >= 2))

    except Exception:
        return []


def compute_rs_and_liquidity(ticker, nifty_return):
    """
    Real RS (excess-over-benchmark, matching RelativeStrengthEngine.py's
    own live formula exactly) and real average turnover, from our own
    backfilled price history.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df.dropna(subset=["close"])

        if len(df) < MIN_TRADING_DAYS_RS:
            return None

        close = df["close"]
        start_close = float(close.iloc[-250])

        if start_close <= 0:
            return None

        rs_raw = (float(close.iloc[-1]) - start_close) / start_close
        excess_return = rs_raw - nifty_return

        avg_turnover = float((df["volume"] * close).tail(20).mean()) if "volume" in df.columns else 0

        return {"rs_excess": excess_return, "turnover": avg_turnover}

    except Exception:
        return None


def run():

    print()
    print("=" * 70)
    print("SECTOR STRENGTH RANKER")
    print("=" * 70)

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    nifty_path = os.path.join(PARQUET_CACHE_DIR, f"{NIFTY_BENCHMARK_SYMBOL}.parquet")
    nifty_return = 0.0

    if os.path.exists(nifty_path):
        ndf = pd.read_parquet(nifty_path)
        if len(ndf) >= 250:
            nifty_return = (float(ndf["close"].iloc[-1]) - float(ndf["close"].iloc[-250])) / float(ndf["close"].iloc[-250])

    print(f"[*] Scanning {len(symbols)} stocks, mapping against {len(SECTOR_UNIVERSE)} "
          f"sector-classified stocks in core/sector_map.py...")

    rows = []

    for symbol in symbols:
        sector = get_sector(symbol)

        if sector == "UNKNOWN":
            continue

        result = compute_rs_and_liquidity(symbol, nifty_return)

        if result is None:
            continue

        rows.append({
            "symbol": symbol,
            "sector": sector,
            "rs_excess": result["rs_excess"],
            "turnover": result["turnover"],
        })

    if not rows:
        print("[+] No sector-mapped stocks had sufficient real history to score.")
        return

    df = pd.DataFrame(rows)

    print(f"[+] {len(df)} sector-mapped stocks with genuinely sufficient history scored.")

    sector_scores = []

    for sector, group in df.groupby("sector"):

        if len(group) < MIN_STOCKS_PER_SECTOR:
            continue

        weights = np.log1p(group["turnover"].clip(lower=0))

        if weights.sum() == 0:
            continue

        weighted_score = (group["rs_excess"] * weights).sum() / weights.sum()

        sector_scores.append({
            "sector": sector,
            "liquidity_weighted_rs": round(weighted_score * 100, 2),
            "stock_count": len(group),
            "avg_rs_excess_pct": round(group["rs_excess"].mean() * 100, 2),
        })

    if not sector_scores:
        print(f"[+] No sector had at least {MIN_STOCKS_PER_SECTOR} mapped stocks - "
              f"nothing statistically meaningful to rank.")
        return

    result_df = pd.DataFrame(sector_scores).sort_values("liquidity_weighted_rs", ascending=False)

    print(f"\n[+] Sector strength ranking ({len(result_df)} sectors, "
          f"minimum {MIN_STOCKS_PER_SECTOR} mapped stocks each):")
    print(result_df.to_string(index=False))

    thin_sectors = result_df[result_df["stock_count"] < 5]
    if not thin_sectors.empty:
        print(f"\n[!] {len(thin_sectors)} sector(s) have fewer than 5 mapped stocks - "
              f"treat these rankings with less confidence than sectors with more coverage:")
        for _, row in thin_sectors.iterrows():
            print(f"    {row['sector']}: only {row['stock_count']} mapped stock(s)")

    print("=" * 70)


if __name__ == "__main__":
    run()