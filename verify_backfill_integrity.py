"""
verify_backfill_integrity.py

Read-only check. Does NOT modify any files.

Scans each stock's RAW Yahoo archive history for internal
discontinuities - a large single-day jump in Yahoo's own close price
that isn't explained by normal daily volatility. That's the real
signature of a dividend/split event Yahoo adjusted for somewhere in its
2-year history, independent of anything the backfill process has done.

Threshold is set at 15% - real NSE stocks routinely move 1-5% in a
single day and occasionally more on genuine news, but essentially never
50%+ except for an actual split/bonus event. Smaller residual offsets
from dividend adjustments buried deep in history are real but
practically harmless for technical indicators (RS, ATR, moving
averages), which depend on recent relative price movement, not absolute
historical price level - old data eventually rolls out of every rolling
window anyway. This check exists to catch the dangerous case (a real,
large, unaccounted-for split), not to chase every small residual.
"""

import os
import glob
import pandas as pd

JUMP_THRESHOLD_PCT = 15.0  # single-day change larger than this is well beyond normal volatility


def scan_for_internal_jumps(yahoo_path):

    df = pd.read_parquet(yahoo_path)
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]

    if "date" not in df.columns or "close" not in df.columns:
        return []

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["pct_change"] = df["close"].pct_change() * 100

    jumps = df[df["pct_change"].abs() >= JUMP_THRESHOLD_PCT]

    return [
        (row["date"].date(), round(row["pct_change"], 2))
        for _, row in jumps.iterrows()
    ]


def verify():

    yahoo_files = glob.glob(os.path.join("parquet_cache_archive_yahoo", "*.parquet"))

    flagged = []

    for yahoo_path in yahoo_files:

        ticker = os.path.basename(yahoo_path).replace(".NS.parquet", "")

        jumps = scan_for_internal_jumps(yahoo_path)

        if jumps:
            flagged.append((ticker, jumps))

    print(f"Scanned {len(yahoo_files)} archived stocks for internal discontinuities.")
    print(f"Flagged: {len(flagged)}")
    print()

    for ticker, jumps in flagged:
        print(f"{ticker}:")
        for date, pct in jumps:
            print(f"    {date}: {pct:+.2f}% single-day move")


if __name__ == "__main__":
    verify()