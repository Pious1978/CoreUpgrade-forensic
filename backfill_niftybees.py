"""
backfill_niftybees.py

NIFTYBEES has no Yahoo archive file to splice from (unlike the ~2,050
regular stocks already backfilled) - it only has 38 real bhav-copy days,
nowhere near the 200 needed for a real SMA200 in Market_Regime_Engine.py.

This downloads real historical daily data directly from Yahoo Finance
for just this one critical ticker, then applies the exact same safety
check as backfill_from_yahoo_archive.py before trusting it: only splice
in the older Yahoo data if it genuinely agrees with real bhav-copy
prices on overlapping dates (catches any hidden split/dividend
adjustment before it can corrupt anything).
"""

import pandas as pd
import yfinance as yf
import os

PARQUET_CACHE_DIR = "parquet_cache"
TICKER = "NIFTYBEES"
OVERLAP_TOLERANCE_PCT = 3.0


def run():

    bhav_path = os.path.join(PARQUET_CACHE_DIR, f"{TICKER}.parquet")

    if not os.path.exists(bhav_path):
        print(f"[-] {bhav_path} not found - nothing to backfill onto.")
        return

    bhav_df = pd.read_parquet(bhav_path)
    bhav_df.columns = [str(c).lower() for c in bhav_df.columns]
    bhav_df["date"] = pd.to_datetime(bhav_df["date"])

    print(f"[*] Downloading real historical data for {TICKER} from Yahoo Finance...")

    yahoo_df = yf.download(f"{TICKER}.NS", period="2y", interval="1d", auto_adjust=False, progress=False)

    if yahoo_df is None or yahoo_df.empty:
        print("[-] Yahoo download returned no data - check your internet connection and try again.")
        return

    if isinstance(yahoo_df.columns, pd.MultiIndex):
        yahoo_df.columns = [c[0].lower() for c in yahoo_df.columns]
    else:
        yahoo_df.columns = [c.lower() for c in yahoo_df.columns]

    yahoo_df = yahoo_df.reset_index()
    yahoo_df.columns = [str(c).lower() for c in yahoo_df.columns]
    yahoo_df["date"] = pd.to_datetime(yahoo_df["date"])

    print(f"[+] Downloaded {len(yahoo_df)} days of real Yahoo history: {yahoo_df['date'].min().date()} to {yahoo_df['date'].max().date()}")

    # Real safety check - same methodology as the original bulk backfill
    merged = pd.merge(
        bhav_df[["date", "close"]].rename(columns={"close": "bhav_close"}),
        yahoo_df[["date", "close"]].rename(columns={"close": "yahoo_close"}),
        on="date", how="inner"
    ).sort_values("date")

    if merged.empty:
        print("[-] No overlapping dates found between bhav copy and Yahoo data - can't safety-check this, aborting.")
        return

    merged["pct_diff"] = ((merged["bhav_close"] - merged["yahoo_close"]).abs() / merged["yahoo_close"]) * 100
    max_diff = merged["pct_diff"].max()

    print(f"[*] Overlap check: {len(merged)} dates compared, max difference {round(max_diff, 3)}%")

    if max_diff > OVERLAP_TOLERANCE_PCT:
        print(f"[!] SKIPPED - overlap mismatch ({round(max_diff,3)}% > {OVERLAP_TOLERANCE_PCT}% tolerance). "
              f"This suggests a real split/adjustment - not safe to splice automatically. Investigate manually.")
        return

    earliest_row = merged.iloc[0]
    correction_factor = earliest_row["bhav_close"] / earliest_row["yahoo_close"]

    bhav_start = bhav_df["date"].min()
    older_yahoo = yahoo_df[yahoo_df["date"] < bhav_start].copy()

    if older_yahoo.empty:
        print("[-] No older Yahoo data before the bhav-copy start date - nothing to add.")
        return

    if max_diff > 0.05:
        for col in ["open", "high", "low", "close"]:
            if col in older_yahoo.columns:
                older_yahoo[col] = older_yahoo[col] * correction_factor
        print(f"[+] Applying correction factor {round(correction_factor, 5)} to older data (dividend-style adjustment detected)")

    older_yahoo["delivery_qty"] = None
    older_yahoo["delivery_pct"] = None

    keep_cols = ["date", "open", "high", "low", "close", "volume", "delivery_qty", "delivery_pct"]
    older_yahoo = older_yahoo[[c for c in keep_cols if c in older_yahoo.columns]]

    for col in keep_cols:
        if col not in bhav_df.columns:
            bhav_df[col] = None

    combined = pd.concat([older_yahoo, bhav_df[keep_cols]], ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates(subset="date", keep="last")

    combined.to_parquet(bhav_path, index=False)

    print(f"[+] {TICKER} extended: {len(combined)} total rows, {combined['date'].min()} to {combined['date'].max()}")


if __name__ == "__main__":
    run()