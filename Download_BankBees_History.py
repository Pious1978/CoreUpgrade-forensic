"""
Download_BankBees_History.py

Real prerequisite for Phase B of the RS redesign: BANKBEES currently
has only 43 real trading days in parquet_cache, nowhere near enough
for a genuine multi-horizon sector benchmark. Downloads its full real
history from Yahoo Finance and saves it into
parquet_cache_archive_yahoo/ in exactly the schema
backfill_from_yahoo_archive.py's normalize_yahoo_file() expects -
confirmed directly against that function before writing this, so the
existing, already-proven merge tool can consume it without any
modification. Does NOT touch parquet_cache/BANKBEES.parquet directly -
that merge step remains backfill_from_yahoo_archive.py's job,
unchanged, exactly as it already works for every other ticker.
"""

import yfinance as yf
import pandas as pd
import os

YAHOO_ARCHIVE_DIR = "parquet_cache_archive_yahoo"


def download_bankbees():

    print()
    print("=" * 70)
    print("DOWNLOAD BANKBEES FULL HISTORY")
    print("=" * 70)

    os.makedirs(YAHOO_ARCHIVE_DIR, exist_ok=True)

    print("[*] Downloading BANKBEES.NS full history from Yahoo Finance...")

    df = yf.download("BANKBEES.NS", period="max", progress=False, auto_adjust=True)

    if df is None or df.empty:
        print("[-] Download failed or returned no data.")
        return

    # yfinance can return a MultiIndex column structure for a single
    # ticker in newer versions - flatten it if present, matching the
    # same defensive handling already established in this system's
    # other yfinance usage tonight.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    output_path = os.path.join(YAHOO_ARCHIVE_DIR, "BANKBEES.NS.parquet")
    df.to_parquet(output_path)

    print(f"[+] Downloaded {len(df)} real rows, {df.index.min().date()} to {df.index.max().date()}")
    print(f"[+] Saved to {output_path}")
    print()
    print("Next step: run backfill_from_yahoo_archive.py as-is to merge")
    print("this into parquet_cache/BANKBEES.parquet, exactly the same")
    print("proven process already used for every other ticker.")
    print("=" * 70)


if __name__ == "__main__":
    download_bankbees()