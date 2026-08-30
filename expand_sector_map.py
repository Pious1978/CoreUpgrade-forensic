"""
expand_sector_map.py

Our current core/sector_map.py only covers ~60 hand-curated stocks -
honest limitation flagged when it was built. This expands real coverage
by downloading NSE's own official sectoral index constituent lists
(Nifty Bank, Nifty IT, Nifty Auto, etc.) - the same real, working URL
pattern already confirmed for the Nifty 500 list in Alpha1's own
scripts (archives.nseindia.com/content/indices/ind_*list.csv).

Lower risk than Universe_Updater.py's live fetch (which corrupted real
data by misdetecting delistings from a partial response) - here, if any
single index fetch fails, we simply get fewer additional stocks. Nothing
existing gets overwritten or deleted; failures are skipped individually
and reported, not silently swallowed.

Existing hand-curated entries in sector_map.py are preserved and take
priority - this only ADDS stocks we don't already have a sector for.
"""

import requests
import pandas as pd
import io
import os

# NSE's real sectoral index constituent list URLs, following the same
# pattern already confirmed working for ind_nifty500list.csv. Some of
# these may not resolve exactly as named - each is fetched and reported
# independently, so a wrong URL here only means that one sector doesn't
# get added, not that anything breaks.
SECTOR_INDEX_URLS = {
    "Banking": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
    "IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
    "Auto": "https://archives.nseindia.com/content/indices/ind_niftyautolist.csv",
    "Pharma": "https://archives.nseindia.com/content/indices/ind_niftypharmalist.csv",
    "FMCG": "https://archives.nseindia.com/content/indices/ind_niftyfmcglist.csv",
    "Metal": "https://archives.nseindia.com/content/indices/ind_niftymetallist.csv",
    "Realty": "https://archives.nseindia.com/content/indices/ind_niftyrealtylist.csv",
    "Energy": "https://archives.nseindia.com/content/indices/ind_niftyenergylist.csv",
    "Media": "https://archives.nseindia.com/content/indices/ind_niftymedialist.csv",
    "Healthcare": "https://archives.nseindia.com/content/indices/ind_niftyhealthcarelist.csv",
    "Financial Services": "https://archives.nseindia.com/content/indices/ind_niftyfinancelist.csv",
    "Oil & Gas": "https://archives.nseindia.com/content/indices/ind_niftyoilgaslist.csv",
    "Consumer Durables": "https://archives.nseindia.com/content/indices/ind_niftyconsumerdurableslist.csv",
    "PSU Bank": "https://archives.nseindia.com/content/indices/ind_niftypsubanklist.csv",
    "Private Bank": "https://archives.nseindia.com/content/indices/ind_niftyprivatebanklist.csv",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/csv",
}


def fetch_sector_constituents(sector_name, url):

    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
        response = session.get(url, headers=HEADERS, timeout=15)

        if response.status_code != 200:
            print(f"  [-] {sector_name}: HTTP {response.status_code} - skipped")
            return {}

        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [c.strip() for c in df.columns]

        symbol_col = None
        for c in df.columns:
            if c.upper().strip() == "SYMBOL":
                symbol_col = c
                break

        if symbol_col is None:
            print(f"  [-] {sector_name}: no SYMBOL column found - skipped")
            return {}

        symbols = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()
        print(f"  [+] {sector_name}: {len(symbols)} constituents fetched")

        return {f"{s}.NS": {"sector": sector_name, "theme": sector_name} for s in symbols}

    except Exception as e:
        print(f"  [-] {sector_name}: {str(e)[:80]} - skipped")
        return {}


def run():

    print("=" * 70)
    print("EXPANDING SECTOR MAP FROM REAL NSE SECTORAL INDEX LISTS")
    print("=" * 70)
    print()

    # Load existing curated entries - these are preserved and take
    # priority over anything fetched here.
    existing = {}
    sector_map_path = os.path.join("core", "sector_map.py")

    if os.path.exists(sector_map_path):
        namespace = {}
        with open(sector_map_path) as f:
            exec(f.read(), namespace)
        existing = namespace.get("UNIVERSE", {})
        print(f"[*] Loaded {len(existing)} existing hand-curated entries\n")

    print("[*] Fetching real NSE sectoral index constituent lists...")

    new_entries = {}
    for sector_name, url in SECTOR_INDEX_URLS.items():
        new_entries.update(fetch_sector_constituents(sector_name, url))

    # Existing curated entries win on any overlap
    combined = {**new_entries, **existing}

    added = len(combined) - len(existing)

    print()
    print(f"[+] Expanded coverage: {len(existing)} -> {len(combined)} stocks (+{added})")

    # Write the new, expanded core/sector_map.py
    output_lines = [
        '"""',
        "core/sector_map.py",
        "",
        "Real sector/theme mapping. Started as a ~60-stock hand-curated set",
        "adapted from Alpha1/nse_universe.py, expanded using NSE's own",
        "official sectoral index constituent lists (expand_sector_map.py).",
        "",
        f"Coverage as of last expansion: {len(combined)} stocks.",
        "Any ticker not in this mapping still falls back to UNKNOWN - the",
        "sector cap only protects candidates within this mapping, not a",
        "comprehensive guarantee across the whole universe.",
        '"""',
        "",
        "UNIVERSE = {",
    ]

    for ticker, info in sorted(combined.items()):
        output_lines.append(f'    "{ticker}": {{"sector": "{info["sector"]}", "theme": "{info["theme"]}"}},')

    output_lines.append("}")
    output_lines.append("")
    output_lines.append("")
    output_lines.append("def get_sector(ticker):")
    output_lines.append('    """Returns the real sector for a ticker if we have it curated,')
    output_lines.append('    otherwise UNKNOWN - callers should treat UNKNOWN as "don\'t apply')
    output_lines.append('    the sector cap to this one, we genuinely don\'t know."""')
    output_lines.append("")
    output_lines.append("    clean = ticker.upper().strip()")
    output_lines.append('    if not clean.endswith(".NS"):')
    output_lines.append('        clean += ".NS"')
    output_lines.append("")
    output_lines.append("    entry = UNIVERSE.get(clean)")
    output_lines.append('    return entry["sector"] if entry else "UNKNOWN"')

    with open(sector_map_path, "w") as f:
        f.write("\n".join(output_lines))

    print(f"[+] Written to {sector_map_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()