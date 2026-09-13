"""
bhav_to_parquet_converter.py

Converts NSE daily bhav copy CSVs (one file per day, all listed securities)
into per-symbol parquet files (one file per symbol, full available time
series) - the format RelativeStrengthEngine, Consolidation_Scanner,
Cup_and_Handle, Emerging_Leader_Scanner, Hybrid_Alpha_Scanner, and
Earnings_Gap_Scanner all read via PARQUET_CACHE_DIR.

Only SERIES == 'EQ' rows are kept (excludes government securities, bonds,
and other non-equity instruments that also appear in the raw bhav copy).

Idempotent for the bhav-covered date range: re-running with the same or
additional bhav copy files regenerates each symbol's parquet file for
every date covered by HistoricalBhavcopies, so there is no risk of
duplicate rows from re-running this on the same date twice.

Preserves older history: if a symbol's existing parquet file has rows
predating the earliest bhav copy (e.g. from backfill_from_yahoo_archive.py),
those older rows are kept, not wiped out. Only the bhav-covered range gets
regenerated fresh each run - anything older than that stays untouched.
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
    preserved_older_history = 0

    for symbol in symbols:
        sym_df = combined[combined["SYMBOL"] == symbol].sort_values("DATE1")

        out = pd.DataFrame({
            "date": sym_df["DATE1"].values,
            # Real bug fix: NSE bhav copies can use "-" (or similar
            # non-numeric placeholders) for missing data in any of
            # these columns - confirmed directly (DELIV_QTY crashed
            # the entire pipeline on a real ' -' value). DELIV_PER
            # already used the correct, robust pattern below; applying
            # it consistently to every numeric column now, rather than
            # only the one that happened to crash first.
            "open": pd.to_numeric(sym_df["OPEN_PRICE"], errors="coerce").values,
            "high": pd.to_numeric(sym_df["HIGH_PRICE"], errors="coerce").values,
            "low": pd.to_numeric(sym_df["LOW_PRICE"], errors="coerce").values,
            "close": pd.to_numeric(sym_df["CLOSE_PRICE"], errors="coerce").values,
            "volume": pd.to_numeric(sym_df["TTL_TRD_QNTY"], errors="coerce").values,
            "delivery_qty": pd.to_numeric(sym_df["DELIV_QTY"], errors="coerce").values,
            "delivery_pct": pd.to_numeric(sym_df["DELIV_PER"], errors="coerce").values,
        })

        # Real, necessary companion to the coercion fix above: without
        # this, a genuinely bad OHLC value (coerced to NaN instead of
        # crashing) would get silently written into parquet_cache as an
        # incomplete row, rather than being dropped. Delivery fields
        # deliberately excluded from this filter - a stock can have a
        # completely valid trading day with missing delivery data.
        before_drop = len(out)
        out = out.dropna(subset=["open", "high", "low", "close"])
        dropped = before_drop - len(out)
        if dropped > 0:
            print(f"  [!] {symbol}: dropped {dropped} row(s) with invalid OHLC data")

        out_path = os.path.join(PARQUET_CACHE_DIR, f"{symbol}.parquet")

        # Preserve any older history already in the file (e.g. from
        # backfill_from_yahoo_archive.py) that predates what this run's
        # bhav copies cover. Only the bhav-covered range gets regenerated.
        if os.path.exists(out_path):
            try:
                existing = pd.read_parquet(out_path)
                existing["date"] = pd.to_datetime(existing["date"])

                bhav_start = out["date"].min()
                older_existing = existing[existing["date"] < bhav_start]

                if not older_existing.empty:
                    out = pd.concat([older_existing, out], ignore_index=True)
                    out = out.sort_values("date").drop_duplicates(subset="date", keep="last")
                    preserved_older_history += 1

            except Exception:
                # If the existing file is unreadable for any reason, fall
                # back to writing fresh bhav-only data rather than crashing
                # the whole conversion run.
                pass

        out.to_parquet(out_path, index=False)
        written += 1

    return {
        "files_read": len(glob.glob(os.path.join(BHAV_DIR, "bhav_*.csv"))),
        "symbols_written": written,
        "symbols_with_preserved_older_history": preserved_older_history,
        "date_range": (
            str(combined["DATE1"].min().date()),
            str(combined["DATE1"].max().date()),
        ),
    }


if __name__ == "__main__":
    result = convert()
    print(f"Bhav copy files read: {result['files_read']}")
    print(f"Symbol parquet files written: {result['symbols_written']}")
    print(f"Symbols with preserved older (backfilled) history: {result['symbols_with_preserved_older_history']}")
    print(f"Date range covered by bhav copies: {result['date_range'][0]} to {result['date_range'][1]}")