"""
Expand_Sector_Coverage.py

The real, structural fix for the sector_map.py coverage gap discussed
throughout tonight - per-stock classification via yfinance's real
.info['sector']/.info['industry'] fields, confirmed reliably working
via Fundamentals_Sanity_Check.py earlier today. Sectoral-index-based
coverage (the current 212 stocks) has a structural ceiling - indices
only ever include NSE's largest, most liquid names, so no amount of
adding more index URLs can reach the full ~2,500+ stock universe. This
is the only path that can.

Two-stage, resumable design given the real scale involved (~2,300
stocks to fetch, each a live network call):

Stage 1 (fetch_missing_sectors): for every universe stock NOT already
in core/sector_map.py's existing 212, fetches real sector/industry via
yfinance, storing results in a SQLite table as it goes. Safe to
interrupt and re-run - already-fetched stocks are skipped, so progress
is never lost. Reuses the exact rate-limiting delay and timeout
protection already proven in Compounder_Scanner.py tonight.

Stage 2 (regenerate_sector_map_file): reads the EXISTING 212 curated
entries (preserved exactly as-is, not re-fetched - they're already
real, index-sourced data) plus every newly-fetched entry from stage 1,
and writes a fresh, expanded core/sector_map.py.
"""

import pandas as pd
import sqlite3
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from core.config import UNIVERSE_CSV_PATH, DB_PATH
from core.sector_map import UNIVERSE as EXISTING_UNIVERSE


def load_universe():
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


def fetch_sector_for_ticker(ticker):
    """
    Real yfinance .info fetch, with the same rate-limiting delay and
    hard timeout protection already proven in Compounder_Scanner.py -
    a single stalled fetch can't freeze this ~2,300-stock run.
    """

    if not YFINANCE_AVAILABLE:
        return None

    def _fetch():
        return yf.Ticker(f"{ticker}.NS").info

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_fetch)
        info = future.result(timeout=15)

        if not info:
            return None

        sector = info.get("sector")
        industry = info.get("industry")

        if not sector:
            return None

        return {"sector": sector, "theme": industry or sector}

    except FuturesTimeoutError:
        return None
    except Exception:
        return None
    finally:
        executor.shutdown(wait=False)


def init_sector_coverage_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_sector_coverage (
            ticker TEXT PRIMARY KEY,
            sector TEXT,
            theme TEXT,
            fetched_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def fetch_missing_sectors():
    """
    Stage 1 - resumable fetch. Already-covered stocks (either in the
    existing 212 curated entries, or already fetched in a previous,
    interrupted run) are skipped entirely.
    """

    init_sector_coverage_table()

    if not YFINANCE_AVAILABLE:
        print("[-] yfinance not available - cannot fetch sector data.")
        return

    universe = load_universe()
    existing_tickers = {t.replace(".NS", "") for t in EXISTING_UNIVERSE.keys()}

    conn = sqlite3.connect(DB_PATH)
    already_fetched = {row[0] for row in conn.execute("SELECT ticker FROM stock_sector_coverage")}
    conn.close()

    to_fetch = [t for t in universe if t not in existing_tickers and t not in already_fetched]

    print(f"[*] {len(existing_tickers)} stocks already covered by the curated 212-stock mapping.")
    print(f"[*] {len(already_fetched)} stocks already fetched in a previous run (resumed).")
    print(f"[*] {len(to_fetch)} stocks remaining to fetch this run.")

    if not to_fetch:
        print("[+] Nothing left to fetch - all stocks already covered.")
        return

    conn = sqlite3.connect(DB_PATH)
    fetched_count = 0
    failed_count = 0

    for i, ticker in enumerate(to_fetch):

        if i > 0 and i % 100 == 0:
            print(f"[*] Progress: {i}/{len(to_fetch)} fetched this run, "
                  f"{fetched_count} succeeded, {failed_count} failed...")
            conn.commit()  # checkpoint periodically, not just at the very end

        result = fetch_sector_for_ticker(ticker)
        time.sleep(0.3)  # same rate-limiting delay proven in Compounder_Scanner.py

        if result:
            conn.execute("""
                INSERT OR REPLACE INTO stock_sector_coverage (ticker, sector, theme, fetched_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (ticker, result["sector"], result["theme"]))
            fetched_count += 1
        else:
            failed_count += 1

    conn.commit()
    conn.close()

    print(f"[+] Stage 1 complete this run: {fetched_count} fetched, {failed_count} failed/no data.")


def regenerate_sector_map_file(output_path="core/sector_map.py"):
    """
    Stage 2 - writes a fresh, expanded core/sector_map.py, preserving
    the existing 212 curated entries exactly as-is (real, index-sourced
    data, not re-fetched) and adding every newly-fetched entry from
    stage 1's accumulated results.
    """

    conn = sqlite3.connect(DB_PATH)
    fetched_rows = conn.execute("SELECT ticker, sector, theme FROM stock_sector_coverage").fetchall()
    conn.close()

    combined = dict(EXISTING_UNIVERSE)
    added = 0

    for ticker, sector, theme in fetched_rows:
        key = f"{ticker}.NS"
        if key not in combined:
            combined[key] = {"sector": sector, "theme": theme}
            added += 1

    print(f"[*] Regenerating sector_map.py: {len(EXISTING_UNIVERSE)} curated + "
          f"{added} newly-fetched = {len(combined)} total stocks.")

    lines = [
        '"""',
        "core/sector_map.py",
        "",
        "Real sector/theme mapping. Started as a ~60-stock hand-curated set,",
        "expanded to 212 via NSE's own official sectoral index constituent",
        "lists, and now further expanded via real, per-stock yfinance",
        f".info['sector'] classification - {len(combined)} stocks total as of",
        "the last expansion. The per-stock approach is what let this reach",
        "far beyond the index-based method's structural ~300-400 stock ceiling.",
        "",
        "Any ticker still not in this mapping falls back to UNKNOWN - the",
        "sector cap only protects candidates within this mapping.",
        '"""',
        "",
        "UNIVERSE = {",
    ]

    for key in sorted(combined.keys()):
        entry = combined[key]
        sector = entry["sector"].replace('"', "'")
        theme = entry["theme"].replace('"', "'")
        lines.append(f'    "{key}": {{"sector": "{sector}", "theme": "{theme}"}},')

    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def get_sector(ticker):")
    lines.append('    """Returns the real sector for a ticker if we have it curated,')
    lines.append('    otherwise UNKNOWN - callers should treat UNKNOWN as "don\'t apply')
    lines.append('    the sector cap to this one, we genuinely don\'t know."""')
    lines.append("")
    lines.append("    clean = ticker.upper().strip()")
    lines.append('    if not clean.endswith(".NS"):')
    lines.append('        clean += ".NS"')
    lines.append("")
    lines.append("    entry = UNIVERSE.get(clean)")
    lines.append('    return entry["sector"] if entry else "UNKNOWN"')
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"[+] Written {len(combined)} stocks to {output_path}")


def run():

    print()
    print("=" * 70)
    print("EXPAND SECTOR COVERAGE - REAL PER-STOCK CLASSIFICATION")
    print("=" * 70)

    fetch_missing_sectors()

    print()
    regenerate_sector_map_file()

    print("=" * 70)


if __name__ == "__main__":
    run()