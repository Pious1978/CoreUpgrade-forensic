"""
Sleeve_Rebalance_Check.py

Addresses #62/#63 - Compounder and HighRisk portfolio lifecycle /
rebalance methodology, confirmed genuinely open by #29's forensic
re-verification. SIP_Allocator.py already defines real stop_loss
thresholds per sleeve (Compounder 20%, HighRisk 5%) but nothing ever
reads them - this is that missing piece.

HONEST, STATED LIMITATION: this system has no real "ActualTrade"
reconciliation layer for SIP purchases (unlike the swing-trading
system's trade_journal) - it estimates cumulative holdings and average
cost by assuming every historical SIP allocation was actually executed
at that month's real closing price. This is a genuine approximation,
not a substitute for tracking real fills - stated explicitly rather
than presented as more precise than it is.

Two real, distinct exit signals per sleeve:
1. Dropped from current candidates - the stock no longer clears the
   sleeve's own quality/momentum gate today, regardless of price.
2. Stop-loss breach - drawdown from estimated average cost exceeds the
   sleeve's own real profile threshold (reused directly from
   SIP_Allocator.py's PROFILES, not a new, separate number).

HighRisk sleeve gets one additional, sleeve-specific signal: a genuine
momentum/trend breakdown (price now below its 200-day MA) - directly
relevant to a momentum-chasing sleeve's own stated thesis, not
meaningful for the Compounder sleeve's different philosophy.
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

from core.config import DB_PATH, PARQUET_CACHE_DIR
from Compounder_Scanner import compute_technical_features
from SIP_Allocator import PROFILES


def estimate_holdings(allocations_table):
    """
    Real, honest estimation of cumulative holdings from SIP_Allocator.py's
    own allocation history - looks up the actual historical closing
    price on each allocation's real date (not just summing rupee
    amounts), computing implied shares bought that month, then a real,
    share-weighted average cost across all months.
    """

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"SELECT ticker, allocation, date FROM {allocations_table}", conn)
        conn.close()
    except Exception:
        return {}

    if df.empty:
        return {}

    holdings = {}

    for ticker, group in df.groupby("ticker"):

        path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")
        if not os.path.exists(path):
            continue

        try:
            price_df = pd.read_parquet(path)
            price_df.columns = [str(c).lower() for c in price_df.columns]
            price_df["date"] = pd.to_datetime(price_df["date"])
            price_df = price_df.set_index("date").sort_index()
        except Exception:
            continue

        total_shares = 0.0
        total_invested = 0.0

        for _, row in group.iterrows():
            alloc_date = pd.Timestamp(row["date"])
            # Real, direct lookup of the actual closing price on (or
            # nearest before) that allocation date - not an invented
            # or averaged price.
            available = price_df.loc[:alloc_date]
            if available.empty:
                continue
            price_on_date = float(available["close"].iloc[-1])
            if price_on_date <= 0:
                continue
            implied_shares = row["allocation"] / price_on_date
            total_shares += implied_shares
            total_invested += row["allocation"]

        if total_shares > 0:
            holdings[ticker] = {
                "avg_cost": round(total_invested / total_shares, 2),
                "total_invested": round(total_invested, 2),
                "total_shares": round(total_shares, 2),
            }

    return holdings


def get_current_candidates(candidates_table):
    """Real, current candidate list from the sleeve's own scanner output."""

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"""
            SELECT ticker FROM {candidates_table}
            WHERE date = (SELECT MAX(date) FROM {candidates_table})
        """, conn)
        conn.close()
        return set(df["ticker"].tolist())
    except Exception:
        return set()


def check_sleeve(sleeve_name, profile_name, allocations_table, candidates_table, check_momentum=False):

    print()
    print("-" * 70)
    print(f"{sleeve_name.upper()} SLEEVE - REBALANCE CHECK")
    print("-" * 70)

    holdings = estimate_holdings(allocations_table)

    if not holdings:
        print(f"[-] No estimated holdings found - run SIP_Allocator.py for this sleeve first.")
        return

    current_candidates = get_current_candidates(candidates_table)
    stop_loss_pct = PROFILES[profile_name]["stop_loss"]

    print(f"[*] {len(holdings)} tickers with estimated holdings, real stop-loss threshold: {stop_loss_pct*100:.0f}%")
    print()

    flagged_count = 0

    for ticker, info in holdings.items():

        flags = []

        if ticker not in current_candidates:
            flags.append("DROPPED FROM CANDIDATES - no longer clears this sleeve's own quality/momentum gate")

        path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")
        current_price = None

        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                df.columns = [str(c).lower() for c in df.columns]
                df = df.dropna(subset=["close"]).sort_values("date")
                current_price = float(df["close"].iloc[-1])
            except Exception:
                pass

        if current_price is not None and info["avg_cost"] > 0:
            drawdown_pct = (current_price - info["avg_cost"]) / info["avg_cost"]
            if drawdown_pct <= -stop_loss_pct:
                flags.append(f"STOP-LOSS BREACH - {drawdown_pct*100:.1f}% below estimated avg cost "
                             f"(Rs{info['avg_cost']:.2f}), exceeds this sleeve's real {stop_loss_pct*100:.0f}% threshold")

        if check_momentum:
            tech = compute_technical_features(ticker)
            if tech and tech.get("trend") == 0:
                flags.append("MOMENTUM BREAKDOWN - price now below its 200-day MA, directly against this sleeve's own momentum thesis")

        if flags:
            flagged_count += 1
            print(f"  {ticker:<15} Rs{info['avg_cost']:.2f} avg cost, "
                  f"Rs{current_price:.2f} now" if current_price else f"  {ticker:<15} (current price unavailable)")
            for f in flags:
                print(f"    ⚠ {f}")

    if flagged_count == 0:
        print("  ✅ No positions flagged for review - all estimated holdings still clear their gate and stop-loss.")
    else:
        print(f"\n[+] {flagged_count} of {len(holdings)} positions flagged for review.")

    print("-" * 70)


def run():

    print()
    print("=" * 70)
    print("SLEEVE REBALANCE CHECK - #62/#63")
    print("=" * 70)
    print("HONEST LIMITATION: holdings and average cost are ESTIMATED from")
    print("SIP_Allocator.py's own allocation history, assuming every")
    print("suggested allocation was actually executed at that month's real")
    print("closing price. This is a genuine approximation, not a substitute")
    print("for tracking real fills.")

    check_sleeve("Core", "Compounder", "sip_allocations_core", "compounder_candidates", check_momentum=False)
    check_sleeve("High-Risk", "HighRisk", "sip_allocations_highrisk", "highrisk_candidates", check_momentum=True)

    print()
    print("=" * 70)


if __name__ == "__main__":
    run()