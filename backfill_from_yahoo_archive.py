"""
backfill_from_yahoo_archive.py (v2)

Extends bhav-copy-derived parquet history with older Yahoo-archive data,
for stocks where it's safe to do so.

Bhav copies only go back to when you started downloading them. The
retired Yahoo-era archive (parquet_cache_archive_yahoo/) has up to 2
years of history per stock - but Yahoo silently back-adjusts historical
prices for dividends (and splits), while bhav copies are always raw/
unadjusted. Splicing them together naively would create a false price
discontinuity that could corrupt every downstream calculation.

v1 of this script rejected ANY stock with more than ~1% average
difference on overlapping dates. Real testing showed this correctly
caught genuine splits (e.g. one stock showed a 360% difference - almost
certainly a real corporate action) but also rejected many stocks with a
small (1-2.5%), highly consistent offset - the exact signature of a
dividend adjustment, confirmed by checking BHARTIARTL's day-by-day
overlap: a constant 1.259% offset on every date before its real
ex-dividend date, dropping to ~0% after it.

v2 distinguishes the two cases by MAXIMUM (not average) overlap
difference: dividend yields on NSE stocks rarely exceed a few percent,
while splits/bonus issues are large, round-number ratios (50%+). Stocks
under DIVIDEND_TOLERANCE_PCT get their older Yahoo prices corrected by
the offset ratio (not spliced in raw) before merging. Stocks above it
are still rejected entirely, same as v1.
"""

import os
import glob
import pandas as pd

from core.config import PARQUET_CACHE_DIR

YAHOO_ARCHIVE_DIR = "parquet_cache_archive_yahoo"
DIVIDEND_TOLERANCE_PCT = 3.0  # max per-date difference still treated as a correctable dividend adjustment, not a split


def normalize_yahoo_file(path):
    """Reads a Yahoo-era parquet file and normalizes it to match the
    bhav-copy schema: lowercase columns, plain date column, delivery
    columns present but null (Yahoo has no delivery data)."""

    df = pd.read_parquet(path)
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]

    if "date" not in df.columns:
        return None

    df["date"] = pd.to_datetime(df["date"])

    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return None

    df["delivery_qty"] = None
    df["delivery_pct"] = None

    return df[["date", "open", "high", "low", "close", "volume", "delivery_qty", "delivery_pct"]]


def check_overlap(bhav_df, yahoo_df):
    """Compares every overlapping date. Returns (max_pct_diff,
    correction_factor, overlap_count). correction_factor is the ratio
    bhav_close/yahoo_close on the EARLIEST overlapping date - this is
    the value that connects to the older, pre-overlap Yahoo data, since
    it's adjacent to where the backfilled history will be spliced in."""

    merged = pd.merge(
        bhav_df[["date", "close"]].rename(columns={"close": "bhav_close"}),
        yahoo_df[["date", "close"]].rename(columns={"close": "yahoo_close"}),
        on="date",
        how="inner",
    ).sort_values("date")

    if merged.empty:
        return None, None, 0

    merged["pct_diff"] = (
        (merged["bhav_close"] - merged["yahoo_close"]).abs()
        / merged["yahoo_close"]
    ) * 100

    max_diff = merged["pct_diff"].max()

    earliest_row = merged.iloc[0]
    correction_factor = earliest_row["bhav_close"] / earliest_row["yahoo_close"]

    return round(max_diff, 3), correction_factor, len(merged)


def backfill():

    bhav_files = glob.glob(os.path.join(PARQUET_CACHE_DIR, "*.parquet"))

    merged_exact = 0
    merged_corrected = 0
    skipped_no_yahoo = 0
    skipped_unsafe = 0
    skipped_no_overlap = 0

    for bhav_path in bhav_files:

        ticker = os.path.basename(bhav_path).replace(".parquet", "")
        yahoo_path = os.path.join(YAHOO_ARCHIVE_DIR, f"{ticker}.NS.parquet")

        if not os.path.exists(yahoo_path):
            skipped_no_yahoo += 1
            continue

        bhav_df = pd.read_parquet(bhav_path)
        bhav_df["date"] = pd.to_datetime(bhav_df["date"])

        yahoo_df = normalize_yahoo_file(yahoo_path)

        if yahoo_df is None:
            skipped_no_yahoo += 1
            continue

        max_diff, correction_factor, overlap_count = check_overlap(bhav_df, yahoo_df)

        if overlap_count == 0:
            skipped_no_overlap += 1
            continue

        if max_diff > DIVIDEND_TOLERANCE_PCT:
            skipped_unsafe += 1
            print(f"  [!] {ticker}: SKIPPED - max {max_diff}% diff over {overlap_count} dates, likely a real split/bonus")
            continue

        bhav_start = bhav_df["date"].min()
        older_yahoo = yahoo_df[yahoo_df["date"] < bhav_start].copy()

        if older_yahoo.empty:
            continue

        if max_diff > 0.05:
            # Real, non-trivial offset detected - correct for it rather
            # than splice raw, dividend-adjusted prices in unmodified.
            for col in ["open", "high", "low", "close"]:
                older_yahoo[col] = older_yahoo[col] * correction_factor
            merged_corrected += 1
            print(f"  [+] {ticker}: backfilled WITH correction (factor {round(correction_factor, 5)}, max diff was {max_diff}%)")
        else:
            merged_exact += 1

        combined = pd.concat([older_yahoo, bhav_df], ignore_index=True)
        combined = combined.sort_values("date").drop_duplicates(subset="date", keep="last")

        combined.to_parquet(bhav_path, index=False)

    print()
    print(f"Backfilled (exact match, no correction needed): {merged_exact}")
    print(f"Backfilled (dividend-style correction applied): {merged_corrected}")
    print(f"Skipped (no Yahoo archive): {skipped_no_yahoo}")
    print(f"Skipped (no overlapping dates to verify): {skipped_no_overlap}")
    print(f"Skipped (likely real split/bonus, max diff > {DIVIDEND_TOLERANCE_PCT}%): {skipped_unsafe}")


if __name__ == "__main__":
    backfill()