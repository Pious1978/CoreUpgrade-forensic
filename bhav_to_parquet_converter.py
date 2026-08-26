"""
bhav_to_parquet_converter.py

Converts NSE daily bhav copy CSVs (one file per day, all listed securities)
into per-symbol parquet files (one file per symbol, full available time
series) - the format RelativeStrengthEngine, Consolidation_Scanner,
Cup_and_Handle, Emerging_Leader_Scanner, Hybrid_Alpha_Scanner, and
Earnings_Gap_Scanner all read via PARQUET_CACHE_DIR.

Only SERIES == 'EQ' rows are kept (excludes government securities, bonds,
and other non-equity instruments that also appear in the raw bhav copy).

Idempotent: re-running with the same or additional bhav copy files
regenerates each symbol's parquet file fully from all available daily
files, rather than appending, so there is no risk of duplicate rows from
re-running this on the same date twice.
"""

import glob
import os
import pandas as pd

from core.config import PARQUET_CACHE_DIR, BASE_DIR

BHAV_DIR = os.path.join(BASE_DIR, "HistoricalBhavcopies")


def _load_all_bhav_files() -> pd.DataFrame:
    """Reads every bhav_*.csv in BHAV_DIR and concatenates into one long
    dataframe, filtered to equity series only.

    Files that don't match the expected equity bhav copy schema (e.g. NSE's
    newer combined/derivatives report format, which has completely different
    columns like TckrSymb/XpryDt/StrkPric instead of SYMBOL/SERIES/DATE1)
    are skipped with a warning rather than aborting the whole conversion.
    """
    files = sorted(glob.glob(os.path.join(BHAV_DIR, "bhav_*.csv")))
    if not files:
        raise FileNotFoundError(f"No bhav_*.csv files found in {BHAV_DIR}")

    required_cols = {
        "SYMBOL", "SERIES", "DATE1", "OPEN_PRICE", "HIGH_PRICE",
        "LOW_PRICE", "CLOSE_PRICE", "TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER",
    }

    frames = []
    skipped = []
    for f in files:
        df = pd.read_csv(f)
        df.columns = [c.strip().upper() for c in df.columns]

        if not required_cols.issubset(set(df.columns)):
            skipped.append(os.path.basename(f))
            continue

        df = df[df["SERIES"].str.strip() == "EQ"].copy()
        frames.append(df)

    if skipped:
        print(f"WARNING: skipped {len(skipped)} file(s) with unexpected schema "
              f"(likely a different NSE report type, not a plain equity bhav copy): {skipped}")

    if not frames:
        raise ValueError("No files matched the expected equity bhav copy schema.")

    combined = pd.concat(frames, ignore_index=True)
    combined["SYMBOL"] = combined["SYMBOL"].str.strip()
    combined["DATE1"] = pd.to_datetime(combined["DATE1"].str.strip(), format="%d-%b-%Y")
    return combined


def convert() -> dict:
    """Runs the conversion. Returns a summary dict with counts."""
    os.makedirs(PARQUET_CACHE_DIR, exist_ok=True)

    combined = _load_all_bhav_files()

    symbols = sorted(combined["SYMBOL"].unique())
    written = 0

    for symbol in symbols:
        sym_df = combined[combined["SYMBOL"] == symbol].sort_values("DATE1")

        out = pd.DataFrame({
            "date": sym_df["DATE1"].values,
            "open": sym_df["OPEN_PRICE"].astype(float).values,
            "high": sym_df["HIGH_PRICE"].astype(float).values,
            "low": sym_df["LOW_PRICE"].astype(float).values,
            "close": sym_df["CLOSE_PRICE"].astype(float).values,
            "volume": sym_df["TTL_TRD_QNTY"].astype(float).values,
            "delivery_qty": sym_df["DELIV_QTY"].astype(float).values,
            "delivery_pct": pd.to_numeric(sym_df["DELIV_PER"], errors="coerce").values,
        })

        out_path = os.path.join(PARQUET_CACHE_DIR, f"{symbol}.parquet")
        out.to_parquet(out_path, index=False)
        written += 1

    return {
        "files_read": len(glob.glob(os.path.join(BHAV_DIR, "bhav_*.csv"))),
        "symbols_written": written,
        "date_range": (
            str(combined["DATE1"].min().date()),
            str(combined["DATE1"].max().date()),
        ),
    }


if __name__ == "__main__":
    result = convert()
    print(f"Bhav copy files read: {result['files_read']}")
    print(f"Symbol parquet files written: {result['symbols_written']}")
    print(f"Date range covered: {result['date_range'][0]} to {result['date_range'][1]}")